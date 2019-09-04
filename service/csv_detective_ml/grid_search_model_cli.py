'''Loads an annotated file and extracts features and tagged types for each resource id

Usage:
    train_model.py <i> <p> <m> [options]

Arguments:
    <i>                                An input file or directory (if dir it will convert all txt files inside).
    <p>                                Path where to find the resource's CSVs
    <m>                                Path where to save the trained pipeline [default: "models/"]
    --num_files NFILES                 Number of files (CSVs) to work with [default: 10:int]
    --num_rows NROWS                   Number of rows per file to use [default: 200:int]
    --cores=<n> CORES                  Number of cores to use [default: 2:int]
    --train_size TRAIN                 Percentage for training . If 1.0, then no testing is done [default: 0.7:float]
'''
# import logging
from itertools import product

import joblib
from argopt import argopt
from sklearn import clone
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer, HashingVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GridSearchCV
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline, FeatureUnion
from xgboost import XGBClassifier

# logger = logging.getLogger()
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler())
from features import ItemSelector, CustomFeatures, ColumnInfoExtractor
# from prediction import PredictColumnInfoExtractor
# from service.csv_detective_ml.utils import header_tokenizer

if __name__ == '__main__':
    parser = argopt(__doc__).parse_args()
    tagged_file_path = parser.i
    csv_folder_path = parser.p
    output_model_path = parser.m
    num_files = parser.num_files
    num_rows = parser.num_rows
    train_size = parser.train_size
    n_cores = int(parser.cores)

    # from csv_detective.explore_csv import routine
    # foo = routine("../03c24270-75ac-4a06-9648-44b6b5a5e0f7.csv", num_rows=100)

    pipeline = Pipeline([
        # Extract column info information from csv

        # Use FeatureUnion to combine the features from subject and body
        ('union', FeatureUnion(
            transformer_list=[

                # Pipeline for pulling custom features from the columns
                ('custom_features', Pipeline([
                    ('selector', ItemSelector(key='per_file_rows')),
                    ('customfeatures', CustomFeatures(n_jobs=n_cores)),
                    ("customvect", DictVectorizer())
                ])),
                #
                # Pipeline for standard bag-of-words models for cell values
                ('cell_features', Pipeline([
                    ('selector', ItemSelector(key='all_columns')),
                    ('count', TfidfVectorizer(ngram_range=(1, 3), analyzer="char_wb", binary=False, max_features=2000)),
                ])),

                # Pipeline for standard bag-of-words models for header values
                ('header_features', Pipeline([
                    ('selector', ItemSelector(key='all_headers')),
                    # ('count', TfidfVectorizer(ngram_range=(4, 4), analyzer="char_wb",
                    #                           binary=False, max_features=2000)),
                    ('hash', HashingVectorizer(n_features=2 ** 2, ngram_range=(3, 3), analyzer="char_wb")),

                ])),

            ],

            # weight components in FeatureUnion
              transformer_weights={
                  'custom_features': 1.6,
                  'cell_features': 1,
                  'header_features': .3,
              },

        )),

        # Use a SVC classifier on the combined features
        ('XG', XGBClassifier(n_jobs=n_cores)),
        # ("MLP", MLPClassifier((512, ))),
        # ("LR", LogisticRegression(n_jobs=n_cores, solver="liblinear", multi_class="auto", class_weight="balanced")),

    ])

    # try:
    # train, test = ColumnInfoExtractor(n_files=num_files, n_rows=num_rows, train_size=train_size,
    #                                         n_jobs=n_cores, column_sample=True).transform(
    #          annotations_file=tagged_file_path,
    #          csv_folder=csv_folder_path)

    # pipeline.fit(train, train["y"])
    grid_search = {
        "n_rows": [10,20,50, 75, 100, 150, 200, 250, 300, 400, 500, 700, 800, 1000],
        "n_files": [100, 300, 500, 700, 1000, 1500, 2000, 2500]

    }
    results_dict = {}
    models_dict = {}

    for n_row, n_file in list(product(*grid_search.values()))[:2]:
        print(f"Testing with n_rows={n_row} and  n_files={n_file}")
        train, test = ColumnInfoExtractor(n_files=n_file, n_rows=n_row, train_size=train_size,
                                        n_jobs=n_cores, column_sample=True).transform(
         annotations_file=tagged_file_path,
         csv_folder=csv_folder_path)
        pipeline.fit(train, train["y"])
        y_test = test["y"]
        y_pred = pipeline.predict(test)
        run_f1 = f1_score(y_true=y_test, y_pred=y_pred, average="macro")
        results_dict[f"{str(n_row)}_{str(n_file)}"] = run_f1
        models_dict[f"{str(n_row)}_{str(n_file)}"] = clone(pipeline)

    # if test is not None:
    #     y_test = test["y"]
    #     y_pred = pipeline.predict(test)
    #     print(classification_report(y_test, y_pred=y_pred))

    # if test_distant is not None:
    #     print("\n\nTEST DISTANT\n\n")
    #     y_test = test_distant["y"]
    #     y_pred = pipeline.predict(test_distant)
    #     print(classification_report(y_test, y_pred=y_pred))

    import json
    json.dump(results_dict, open("results.dict.json", "w"))

    sorted_grid = sorted(results_dict.items(), key=lambda x:x[1], reverse=True)
    best_config = sorted_grid[0][0]


    # Save pipeline


    joblib.dump(models_dict[best_config], output_model_path + '/best_GS_model.joblib')

    # from prediction import PredictColumnInfoExtractor
    #
    # ext = PredictColumnInfoExtractor()
    # foo = ext.transform("../03c24270-75ac-4a06-9648-44b6b5a5e0f7.csv")
    # y_pred = pipeline.predict(foo)
    # print(y_pred)
    # pass