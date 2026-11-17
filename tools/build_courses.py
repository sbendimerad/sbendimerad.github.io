#!/usr/bin/env python3
"""Build the course pages from the course repos.

Usage:
    python3 tools/build_courses.py python <path-to-python-repo> [math <path-to-math-repo> ...]

Each course repo is the source of truth: content fixes are made there, on its `website`
branch, and every notebook is run (tools/run_notebooks.py) before it is pushed.
This script only reads the repos and generates, for each section of a course:

  courses/<course>/<NN-section>/lessons/<slug>.ipynb      one page per lesson notebook
  courses/<course>/<NN-section>/exercises/<slug>.ipynb    one page per exercise notebook, hints folded,
                                                         a "Solution →" link after each exercise
  courses/<course>/<NN-section>/solutions/<slug>.ipynb    the matching solutions
  courses/<course>/<NN-section>/img/                       images used by the notebooks
  courses/<course>/files/<NN-section>.zip                  lessons + exercises + data (never solutions)
  courses/<course>/index.qmd                               course overview
  courses/_sidebars.yml                                    sidebar of every built course

Safety nets on the published copy: Jedha links / Jedha-hosted images dropped, outputs with
email addresses dropped, unclosed code blocks closed, very long outputs shortened, saved
Plotly figures redrawn from their data. A privacy scan and a solution-link check run at the
end and fail the build.
"""
import base64, copy, difflib, json, re, shutil, sys, zipfile
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent

COURSES = {
    "python": {
        "title": "Python",
        "number": "01",
        "subtitle": "Course 01 · no prerequisites",
        "intro": "From your first variable to calling an API, in five sections. Each section has a "
                 "**lesson** to read, **exercises** to try on your own (with hints if you are stuck) "
                 "and their **solutions**.",
        "sections": [
            {"slug": "python-basics", "title": "Python basics",
             "description": "Types, operators, strings, data structures, conditions, loops and functions.",
             "lessons": [{"path": "P01_python_basics/course/S1_python_basics_course.ipynb"}],
             "exercises": [{"slug": "python-basics", "title": "Python basics",
                            "exercise": "P01_python_basics/exercises/S1_python_basics_exercises.ipynb",
                            "solution": "P01_python_basics/solutions/S1_python_basics_solutions.ipynb"}]},
            {"slug": "numpy-pandas", "title": "NumPy and pandas",
             "description": "Arrays with NumPy, then loading, cleaning, combining and reshaping tables with pandas.",
             "lessons": [{"path": "P02_eda_viz/course/S2_numpy_pandas_course.ipynb"}],
             "exercises": [{"slug": "numpy", "title": "NumPy",
                            "exercise": "P02_eda_viz/exercises/S2_numpy_exercises.ipynb",
                            "solution": "P02_eda_viz/solutions/S2_numpy_solutions.ipynb"},
                           {"slug": "house-market", "title": "House market (pandas)",
                            "exercise": "P02_eda_viz/exercises/S2_pandas_exercises.ipynb",
                            "solution": "P02_eda_viz/solutions/S2_pandas_solutions.ipynb"},
                           {"slug": "starbucks-reviews", "title": "Starbucks reviews (dates)",
                            "exercise": "P02_eda_viz/exercises/S2_datetime.ipynb",
                            "solution": "P02_eda_viz/solutions/S2_datetime_solutions.ipynb"}]},
            {"slug": "data-visualization", "title": "Data visualisation",
             "description": "Exploring a dataset with Plotly Express: distributions, comparisons, relationships.",
             "lessons": [{"path": "P02_eda_viz/course/S3_visualization_course.ipynb"}],
             "exercises": [{"slug": "ibm-employees", "title": "IBM employees",
                            "exercise": "P02_eda_viz/exercises/S3_visualization_exercises.ipynb",
                            "solution": "P02_eda_viz/solutions/S3_visualization_solutions.ipynb"}]},
            {"slug": "interactive-charts", "title": "Interactive charts",
             "description": "Subplots, sliders, dropdowns and animations with plotly.graph_objects.",
             "lessons": [{"path": "P02_eda_viz/course/S3_visualization_advanced_course.ipynb"}],
             "exercises": [{"slug": "earthquakes", "title": "Earthquakes",
                            "exercise": "P02_eda_viz/exercises/S3_visualization_advanced_exercises.ipynb",
                            "solution": "P02_eda_viz/solutions/S3_visualization_advanced_solutions.ipynb"}]},
            {"slug": "apis", "title": "Working with APIs",
             "description": "What an API is, and how to call one from Python with requests.",
             "lessons": [{"path": "P03_api/course/S4_api_course.ipynb"}],
             "exercises": [{"slug": "bitcoin", "title": "Bitcoin prices",
                            "exercise": "P03_api/exercises/S4_api_exercises.ipynb",
                            "solution": "P03_api/solutions/S4_api_solutions.ipynb"}]},
        ],
    },
    "math": {
        "title": "Math for AI",
        "number": "02",
        "subtitle": "Course 02 · after Python",
        "intro": "The mathematics behind machine learning, with Python: linear algebra, derivatives and "
                 "gradient descent, then statistics. Each section has a **lesson**; many also have "
                 "**exercises** and their **solutions**.",
        "sections": [
            {"part": "Linear algebra", "slug": "numpy-arrays", "title": "NumPy arrays",
             "description": "Create, index, reshape and combine arrays: the building block of linear algebra in Python.",
             "lessons": [{"path": "01_linear_algebra/course/S1_numpy_arrays.ipynb"}], "exercises": [],
             "quiz": "01_linear_algebra/quiz/S1_numpy_arrays_quiz.md"},
            {"part": "Linear algebra", "slug": "linear-systems-2", "title": "Linear systems in 2 variables",
             "description": "Write a system as a matrix, compute its determinant, solve it by elimination.",
             "lessons": [{"path": "01_linear_algebra/course/S2_solving_linear_systems_2_variables.ipynb"}], "exercises": [],
             "quiz": "01_linear_algebra/quiz/S2_linear_systems_2_variables_quiz.md"},
            {"part": "Linear algebra", "slug": "linear-systems-3", "title": "Linear systems in 3 variables",
             "description": "The same tools in three dimensions, with row reduction.",
             "lessons": [{"path": "01_linear_algebra/course/S3_solving_linear_systems_3_variables.ipynb"}], "exercises": [],
             "quiz": "01_linear_algebra/quiz/S3_linear_systems_3_variables_quiz.md"},
            {"part": "Linear algebra", "slug": "matrix-multiplication", "title": "Matrix multiplication",
             "description": "The definition, how to compute it with NumPy, and broadcasting.",
             "lessons": [{"path": "01_linear_algebra/course/S4_matrix_multiplication.ipynb"}], "exercises": [],
             "quiz": "01_linear_algebra/quiz/S4_matrix_multiplication_quiz.md"},
            {"part": "Linear algebra", "slug": "vector-operations", "title": "Vector operations",
             "description": "Scalar multiplication, sum of vectors, norm and dot product, and why vectorised code is faster.",
             "lessons": [{"path": "01_linear_algebra/course/S5_vector_operations.ipynb"}], "exercises": [],
             "quiz": "01_linear_algebra/quiz/S5_vector_operations_quiz.md"},
            {"part": "Linear algebra", "slug": "linear-transformations", "title": "Linear transformations",
             "description": "What makes a transformation linear, and how matrices move the plane.",
             "lessons": [{"path": "01_linear_algebra/course/S6_linear_transformations.ipynb"}], "exercises": [],
             "quiz": "01_linear_algebra/quiz/S6_linear_transformations_quiz.md"},
            {"part": "Linear algebra", "slug": "pca", "title": "Principal component analysis (PCA)",
             "description": "Reduce the number of columns while keeping most of the information.",
             "lessons": [{"slug": "pca-introduction", "title": "PCA: the idea",
                          "path": "01_linear_algebra/course/S7_pca_introduction.ipynb"},
                         {"slug": "pca-with-scikit-learn", "title": "PCA with scikit-learn",
                          "path": "01_linear_algebra/course/S7_pca_sklearn.ipynb"}],
             "exercises": [{"slug": "house-prices", "title": "House prices",
                            "exercise": "01_linear_algebra/exercises/S7_pca_exercice.ipynb",
                            "solution": "01_linear_algebra/solutions/S7_pca_solution.ipynb"}]},
            {"part": "Calculus", "slug": "derivatives", "title": "Derivatives in Python",
             "description": "Symbolic, numerical and automatic differentiation, and their limits.",
             "lessons": [{"path": "02_calculus/course/S1_differentiation_in_python.ipynb"}], "exercises": [],
             "quiz": "02_calculus/quiz/S1_derivatives_quiz.md"},
            {"part": "Calculus", "slug": "gradient-descent-1d", "title": "Gradient descent in one variable",
             "description": "Find the minimum of a function step by step, and see what the learning rate changes.",
             "lessons": [{"path": "02_calculus/course/S2_optimization_gradient_gescent_one_variables.ipynb"}], "exercises": [],
             "quiz": "02_calculus/quiz/S2_gradient_descent_one_variable_quiz.md"},
            {"part": "Calculus", "slug": "gradient-descent-2d", "title": "Gradient descent in two variables",
             "description": "The same method on surfaces, with local and global minima.",
             "lessons": [{"path": "02_calculus/course/S3_optimization_gradient_gescent_two_variables.ipynb"}], "exercises": [],
             "quiz": "02_calculus/quiz/S3_gradient_descent_two_variables_quiz.md"},
            {"part": "Statistics", "slug": "statistics-basics", "title": "Statistics basics",
             "description": "Data types, centre and spread of a distribution, the normal distribution.",
             "lessons": [{"path": "03_statistics/course/S1_statistics_intro.ipynb"}], "exercises": [],
             "quiz": "03_statistics/quiz/S1_statistics_basics_quiz.md"},
            {"part": "Statistics", "slug": "confidence-intervals", "title": "Confidence intervals",
             "description": "Estimate a population mean from a sample, and visualise the uncertainty.",
             "lessons": [{"slug": "confidence-intervals", "title": "Confidence intervals",
                          "path": "03_statistics/course/S2_confidence_intervals.ipynb"},
                         {"slug": "visualise-with-seaborn", "title": "Visualise them with seaborn",
                          "path": "03_statistics/course/S3_visualize_confidence_intervals_seaborn.ipynb"}],
             "exercises": [{"slug": "estimates-and-sampling", "title": "Estimates and sampling",
                            "exercise": "03_statistics/exercises/S2_confidence_intervals.ipynb",
                            "solution": "03_statistics/solutions/S2_confidence_intervals_solution.ipynb"}]},
            {"part": "Statistics", "slug": "hypothesis-testing", "title": "Hypothesis testing",
             "description": "H₀ and H₁, z-scores, p-values, and one- or two-tailed tests.",
             "lessons": [{"path": "03_statistics/course/S4_hypothesis_testing.ipynb"}],
             "exercises": [{"slug": "loan-control", "title": "Loan control (Qonto)",
                            "exercise": "03_statistics/exercises/S4_hypothesis_testing_part1.ipynb",
                            "solution": "03_statistics/solutions/S4_hypothesis_testing_part1_solution_solution.ipynb"},
                           {"slug": "useless-card", "title": "The most useless card (Swile)",
                            "exercise": "03_statistics/exercises/S3_hypothesis_testing_part2.ipynb",
                            "solution": "03_statistics/solutions/S3_hypothesis_testing_part2_solution.ipynb"}]},
            {"part": "Statistics", "slug": "ab-testing", "title": "A/B testing",
             "description": "Design an A/B test and decide with a statistical test.",
             "lessons": [{"path": "03_statistics/course/S5_ab_testing.ipynb"}],
             "exercises": [{"slug": "airbnb", "title": "Homepage background (Airbnb)",
                            "exercise": "03_statistics/exercises/S5_ab_testing_part1.ipynb",
                            "solution": "03_statistics/solutions/S5_ab_testing_part1_solution.ipynb"},
                           {"slug": "vinted", "title": "Call-to-action button (Vinted)",
                            "exercise": "03_statistics/exercises/S5_ab_testing_part2.ipynb",
                            "solution": "03_statistics/solutions/S5_ab_testing_part2_solution.ipynb"}]},
        ],
    },
    "ml": {
        "title": "Supervised Machine Learning",
        "number": "03",
        "subtitle": "Course 03 · after Math for AI",
        "intro": "Predict a number or a category from data: preprocessing, linear and logistic regression, "
                 "regularization, trees, forests and boosting, Naive Bayes and time series, then two projects. "
                 "Each section has **lessons**, a **quiz**, **exercises** and their **solutions**.",
        "sections": [
            {"part": "Foundations", "slug": "preprocessing", "title": "Preprocessing",
             "description": "What machine learning is, and how to prepare data for a model with pandas and scikit-learn.",
             "lessons": [{"slug": "what-is-machine-learning", "title": "What is machine learning?",
                          "path": "supervised/01_preprocessing/course/01-introduction_to_machine_learning.ipynb"},
                         {"slug": "preprocessing-with-pandas", "title": "Preprocessing with pandas",
                          "path": "supervised/01_preprocessing/course/02-what_is_preprocessing.ipynb"},
                         {"slug": "preprocessing-with-scikit-learn", "title": "Preprocessing with scikit-learn",
                          "path": "supervised/01_preprocessing/course/03-preprocessing_with_scikit_learn.ipynb"}],
             "exercises": [{"slug": "titanic", "title": "Titanic",
                            "exercise": "supervised/01_preprocessing/exercises/01-preprocessing_titanic.ipynb",
                            "solution": "supervised/01_preprocessing/solutions/01-preprocessing_titanic_solution.ipynb"},
                           {"slug": "advanced-preprocessing", "title": "Advanced preprocessing (optional)",
                            "exercise": "supervised/01_preprocessing/exercises/02-advanced_preprocessing.ipynb",
                            "solution": "supervised/01_preprocessing/solutions/02-advanced_preprocessing_solution.ipynb"}],
             "quiz": "supervised/01_preprocessing/quiz/preprocessing_quiz.md"},
            {"part": "Regression", "slug": "linear-regression", "title": "Linear regression",
             "description": "Simple and multiple linear regression, R², feature selection, and the full workflow in scikit-learn.",
             "lessons": [{"slug": "linear-regression", "title": "Linear regression",
                          "path": "supervised/02_linear_regression/course/01-linear_regression.ipynb"},
                         {"slug": "performance-and-feature-selection", "title": "Performance and feature selection",
                          "path": "supervised/02_linear_regression/course/02-performance_and_feature_selection.ipynb"},
                         {"slug": "maximum-likelihood", "title": "Optional: maximum likelihood",
                          "path": "supervised/02_linear_regression/course/03-optional_maximum_likelihood.ipynb"},
                         {"slug": "workflow", "title": "Linear regression with scikit-learn",
                          "path": "supervised/02_linear_regression/course/04-linear_regression_workflow.ipynb"},
                         {"slug": "computing-metrics", "title": "Optional: computing the metrics",
                          "path": "supervised/02_linear_regression/course/05-optional_computing_metrics.ipynb"}],
             "exercises": [{"slug": "california-housing", "title": "California housing",
                            "exercise": "supervised/02_linear_regression/exercises/01-california_housing.ipynb",
                            "solution": "supervised/02_linear_regression/solutions/01-california_housing_solution.ipynb"},
                           {"slug": "feature-engineering", "title": "Feature engineering",
                            "exercise": "supervised/02_linear_regression/exercises/02-feature_engineering.ipynb",
                            "solution": "supervised/02_linear_regression/solutions/02-feature_engineering_solution.ipynb"}],
             "quiz": "supervised/02_linear_regression/quiz/linear_regression_quiz.md"},
            {"part": "Regression", "slug": "regularization", "title": "Regularization",
             "description": "Fight overfitting with Ridge and Lasso, and tune hyperparameters with cross-validation and grid search.",
             "lessons": [{"slug": "regularization", "title": "Ridge and Lasso",
                          "path": "supervised/03_regularization/course/01-regularization.ipynb"},
                         {"slug": "cross-validation-and-grid-search", "title": "Cross-validation and grid search",
                          "path": "supervised/03_regularization/course/02-cross_validation_and_grid_search.ipynb"},
                         {"slug": "workflow", "title": "Regularization with scikit-learn",
                          "path": "supervised/03_regularization/course/03-regularization_workflow.ipynb"}],
             "exercises": [{"slug": "ridge-vs-lasso", "title": "Ridge vs. Lasso (gene expression)",
                            "exercise": "supervised/03_regularization/exercises/01-ridge_vs_lasso.ipynb",
                            "solution": "supervised/03_regularization/solutions/01-ridge_vs_lasso_solution.ipynb"},
                           {"slug": "handling-overfitting", "title": "Handling overfitting",
                            "exercise": "supervised/03_regularization/exercises/02-handling_overfitting.ipynb",
                            "solution": "supervised/03_regularization/solutions/02-handling_overfitting_solution.ipynb"}],
             "quiz": "supervised/03_regularization/quiz/regularization_quiz.md"},
            {"part": "Classification", "slug": "logistic-regression", "title": "Logistic regression",
             "description": "Predict a category with probabilities, and evaluate a classifier: confusion matrix, precision, recall, ROC.",
             "lessons": [{"slug": "logistic-regression", "title": "Logistic regression",
                          "path": "supervised/04_logistic_regression/course/01-logistic_regression.ipynb"},
                         {"slug": "workflow", "title": "Classification with scikit-learn",
                          "path": "supervised/04_logistic_regression/course/02-classification_workflow.ipynb"}],
             "exercises": [{"slug": "first-classification", "title": "First classification",
                            "exercise": "supervised/04_logistic_regression/exercises/01-first_classification.ipynb",
                            "solution": "supervised/04_logistic_regression/solutions/01-first_classification_solution.ipynb"},
                           {"slug": "vinho-verde", "title": "Vinho verde",
                            "exercise": "supervised/04_logistic_regression/exercises/02-vinho_verde.ipynb",
                            "solution": "supervised/04_logistic_regression/solutions/02-vinho_verde_solution.ipynb"}],
             "quiz": "supervised/04_logistic_regression/quiz/logistic_regression_quiz.md"},
            {"part": "Classification", "slug": "trees-and-forests", "title": "Decision trees and random forests",
             "description": "How a tree splits the data, why it overfits, and how a forest of trees fixes it.",
             "lessons": [{"slug": "decision-trees", "title": "Decision trees",
                          "path": "supervised/05_trees_and_forests/course/01-decision_trees.ipynb"},
                         {"slug": "random-forest", "title": "Random forests",
                          "path": "supervised/05_trees_and_forests/course/02-random_forest.ipynb"},
                         {"slug": "workflow", "title": "Trees and forests with scikit-learn",
                          "path": "supervised/05_trees_and_forests/course/03-trees_and_forests_workflow.ipynb"},
                         {"slug": "summary-decision-trees", "title": "Summary: decision trees",
                          "path": "supervised/05_trees_and_forests/course/04-summary_decision_trees.ipynb"},
                         {"slug": "summary-random-forest", "title": "Summary: random forests",
                          "path": "supervised/05_trees_and_forests/course/05-summary_random_forest.ipynb"}],
             "exercises": [{"slug": "build-a-decision-tree", "title": "Build a decision tree",
                            "exercise": "supervised/05_trees_and_forests/exercises/01-build_a_decision_tree.ipynb",
                            "solution": "supervised/05_trees_and_forests/solutions/01-build_a_decision_tree_solution.ipynb"},
                           {"slug": "uber-fares", "title": "Uber fares",
                            "exercise": "supervised/05_trees_and_forests/exercises/02-uber_fares.ipynb",
                            "solution": "supervised/05_trees_and_forests/solutions/02-uber_fares_solution.ipynb"}],
             "quiz": "supervised/05_trees_and_forests/quiz/trees_and_forests_quiz.md"},
            {"part": "Classification", "slug": "ensemble-methods", "title": "Ensemble methods",
             "description": "Boosting (AdaBoost, gradient boosting, XGBoost), voting and stacking.",
             "lessons": [{"slug": "boosting", "title": "Boosting",
                          "path": "supervised/06_ensemble_methods/course/01-boosting.ipynb"},
                         {"slug": "voting-and-stacking", "title": "Voting and stacking",
                          "path": "supervised/06_ensemble_methods/course/02-voting_and_stacking.ipynb"},
                         {"slug": "summary-of-boosting", "title": "Summary: boosting",
                          "path": "supervised/06_ensemble_methods/course/03-summary_of_boosting.ipynb"},
                         {"slug": "workflow", "title": "Ensemble methods with scikit-learn",
                          "path": "supervised/06_ensemble_methods/course/04-ensemble_methods_workflow.ipynb"}],
             "exercises": [{"slug": "titanic", "title": "Titanic",
                            "exercise": "supervised/06_ensemble_methods/exercises/01-ensembles_titanic.ipynb",
                            "solution": "supervised/06_ensemble_methods/solutions/01-ensembles_titanic_solution.ipynb"},
                           {"slug": "airbnb", "title": "Airbnb prices",
                            "exercise": "supervised/06_ensemble_methods/exercises/02-ensembles_airbnb.ipynb",
                            "solution": "supervised/06_ensemble_methods/solutions/02-ensembles_airbnb_solution.ipynb"},
                           {"slug": "stars-and-galaxies", "title": "Stars, galaxies and quasars",
                            "exercise": "supervised/06_ensemble_methods/exercises/03-sdss_boosting.ipynb",
                            "solution": "supervised/06_ensemble_methods/solutions/03-sdss_boosting_solution.ipynb"}],
             "quiz": "supervised/06_ensemble_methods/quiz/ensemble_methods_quiz.md"},
            {"part": "Classification", "slug": "naive-bayes", "title": "Naive Bayes",
             "description": "Bayes' theorem and the Naive Bayes classifier, then fraud detection.",
             "lessons": [{"path": "supervised/08_naive_bayes/course/01-naive_bayes.ipynb"}],
             "exercises": [{"slug": "diabetes", "title": "Diabetes",
                            "exercise": "supervised/08_naive_bayes/exercises/01-diabetes.ipynb",
                            "solution": "supervised/08_naive_bayes/solutions/01-diabetes_solution.ipynb"},
                           {"slug": "fraud-detection", "title": "Fraud detection",
                            "exercise": "supervised/08_naive_bayes/exercises/02-fraud_detection.ipynb",
                            "solution": "supervised/08_naive_bayes/solutions/02-fraud_detection_solution.ipynb"}],
             "quiz": "supervised/08_naive_bayes/quiz/naive_bayes_quiz.md"},
            {"part": "Time series", "slug": "time-series", "title": "Time series",
             "description": "Smoothing, stationarity and autocorrelation, then forecasting with Prophet.",
             "lessons": [{"slug": "time-series", "title": "Time series analysis",
                          "path": "supervised/07_time_series/course/01-time_series.ipynb"},
                         {"slug": "prophet", "title": "Forecasting with Prophet",
                          "path": "supervised/07_time_series/course/02-prophet.ipynb"}],
             "exercises": [{"slug": "electricity", "title": "Electricity consumption",
                            "exercise": "supervised/07_time_series/exercises/01-energy_consumption_prophet.ipynb",
                            "solution": "supervised/07_time_series/solutions/01-energy_consumption_prophet_solution.ipynb"},
                           {"slug": "netflix-and-covid", "title": "Netflix and the Covid crisis",
                            "exercise": "supervised/07_time_series/exercises/02-netflix_vs_covid.ipynb",
                            "solution": "supervised/07_time_series/solutions/02-netflix_vs_covid_solution.ipynb"}],
             "quiz": "supervised/07_time_series/quiz/time_series_quiz.md"},
            {"part": "Projects", "slug": "walmart-sales", "title": "Project: Walmart sales",
             "description": "Predict the weekly sales of stores with linear models, and fight overfitting.",
             "lessons": [{"path": "supervised/projects/walmart_sales/walmart_sales.ipynb"}],
             "exercises": [{"slug": "walmart-sales", "title": "Walmart sales",
                            "solution": "supervised/projects/walmart_sales/walmart_sales_solution.ipynb"}]},
            {"part": "Projects", "slug": "conversion-challenge", "title": "Challenge: predict conversions",
             "description": "A competition: predict who subscribes to a newsletter, submit your predictions, climb the leaderboard.",
             "lessons": [{"slug": "the-challenge", "title": "The challenge",
                          "path": "supervised/projects/conversion_rate_challenge/conversion_rate_challenge.ipynb"},
                         {"slug": "starter-notebook", "title": "Starter notebook",
                          "path": "supervised/projects/conversion_rate_challenge/conversion_rate_template.ipynb"}],
             "exercises": []},
        ],
    },
    "uml": {
        "title": "Unsupervised Machine Learning",
        "number": "04",
        "subtitle": "Course 04 · after Supervised Machine Learning",
        "intro": "Find structure in data without labels: clustering with K-Means and DBSCAN, dimensionality reduction "
                 "with PCA, then text: NLP basics and topic modeling, and a project. "
                 "Each section has **lessons**, a **quiz**, **exercises** and their **solutions**.",
        "sections": [
            {"part": "Clustering", "slug": "kmeans", "title": "K-Means",
             "description": "Group similar observations: the K-Means algorithm step by step, then choosing the number of clusters.",
             "lessons": [{"slug": "kmeans", "title": "K-Means",
                          "path": "unsupervised/01_kmeans/course/01-kmeans.ipynb"},
                         {"slug": "workflow", "title": "K-Means with scikit-learn",
                          "path": "unsupervised/01_kmeans/course/02-kmeans_with_scikit_learn.ipynb"}],
             "exercises": [{"slug": "know-your-customers", "title": "Know your customers",
                            "exercise": "unsupervised/01_kmeans/exercises/01-know_your_customers.ipynb",
                            "solution": "unsupervised/01_kmeans/solutions/01-know_your_customers_solution.ipynb"},
                           {"slug": "digits", "title": "Handwritten digits",
                            "exercise": "unsupervised/01_kmeans/exercises/02-digits.ipynb",
                            "solution": "unsupervised/01_kmeans/solutions/02-digits_solution.ipynb"}],
             "quiz": "unsupervised/01_kmeans/quiz/kmeans_quiz.md"},
            {"part": "Clustering", "slug": "dbscan", "title": "DBSCAN",
             "description": "Density-based clustering: clusters of any shape, and noise points.",
             "lessons": [{"slug": "dbscan", "title": "DBSCAN",
                          "path": "unsupervised/02_dbscan/course/01-dbscan.ipynb"},
                         {"slug": "workflow", "title": "DBSCAN with scikit-learn",
                          "path": "unsupervised/02_dbscan/course/02-dbscan_with_scikit_learn.ipynb"}],
             "exercises": [{"slug": "911-emergencies", "title": "911 emergencies",
                            "exercise": "unsupervised/02_dbscan/exercises/01-911_emergencies.ipynb",
                            "solution": "unsupervised/02_dbscan/solutions/01-911_emergencies_solution.ipynb"}],
             "quiz": "unsupervised/02_dbscan/quiz/dbscan_quiz.md"},
            {"part": "Dimensionality reduction", "slug": "pca", "title": "Principal component analysis",
             "description": "Reduce the number of variables while keeping most of the information.",
             "lessons": [{"slug": "pca", "title": "Principal component analysis",
                          "path": "unsupervised/03_pca/course/01-pca.ipynb"},
                         {"slug": "workflow", "title": "PCA with scikit-learn",
                          "path": "unsupervised/03_pca/course/02-pca_with_scikit_learn.ipynb"}],
             "exercises": [{"slug": "house-prices", "title": "House prices",
                            "exercise": "unsupervised/03_pca/exercises/01-house_prices.ipynb",
                            "solution": "unsupervised/03_pca/solutions/01-house_prices_solution.ipynb"},
                           {"slug": "noise-cancellation", "title": "Noise cancellation",
                            "exercise": "unsupervised/03_pca/exercises/02-noise_cancellation.ipynb",
                            "solution": "unsupervised/03_pca/solutions/02-noise_cancellation_solution.ipynb"}],
             "quiz": "unsupervised/03_pca/quiz/pca_quiz.md"},
            {"part": "Text", "slug": "nlp", "title": "Natural language processing",
             "description": "Turn texts into numbers: cleaning, tokens, lemmas, bag of words and TF-IDF.",
             "lessons": [{"slug": "nlp-basics", "title": "NLP basics",
                          "path": "unsupervised/04_nlp/course/01-nlp_basics.ipynb"},
                         {"slug": "workflow", "title": "NLP with spaCy and scikit-learn",
                          "path": "unsupervised/04_nlp/course/02-nlp_with_spacy_and_scikit_learn.ipynb"}],
             "exercises": [{"slug": "obi-wan-kenobi", "title": "Obi-Wan Kenobi",
                            "exercise": "unsupervised/04_nlp/exercises/01-obi_wan_kenobi.ipynb",
                            "solution": "unsupervised/04_nlp/solutions/01-obi_wan_kenobi_solution.ipynb"}],
             "quiz": "unsupervised/04_nlp/quiz/nlp_quiz.md"},
            {"part": "Text", "slug": "topic-modeling", "title": "Topic modeling",
             "description": "Find the hidden topics of a collection of texts with latent semantic analysis (LSA).",
             "lessons": [{"slug": "lsa", "title": "Latent semantic analysis",
                          "path": "unsupervised/05_topic_modeling/course/01-lsa.ipynb"},
                         {"slug": "workflow", "title": "LSA with scikit-learn",
                          "path": "unsupervised/05_topic_modeling/course/02-lsa_with_scikit_learn.ipynb"}],
             "exercises": [{"slug": "topic-modeling", "title": "Topic modeling",
                            "exercise": "unsupervised/05_topic_modeling/exercises/01-topic_modeling.ipynb",
                            "solution": "unsupervised/05_topic_modeling/solutions/01-topic_modeling_solution.ipynb"}],
             "quiz": "unsupervised/05_topic_modeling/quiz/topic_modeling_quiz.md"},
            {"part": "Projects", "slug": "uber-pickups", "title": "Project: Uber pickups",
             "description": "Find the hot zones of New York for each day and hour with K-Means and DBSCAN.",
             "lessons": [{"path": "unsupervised/projects/uber_pickups/uber_pickups.ipynb"}],
             "exercises": [{"slug": "uber-pickups", "title": "Uber pickups",
                            "solution": "unsupervised/projects/uber_pickups/uber_pickups_solution.ipynb"}]},
        ],
    },
}

BLOCKED_HOSTS = ("jedha", "fullstack-assets", "full-stack-assets", "essentials-assets")
MAX_TEXT_LINES = 40
MAX_HTML_BYTES = 1_000_000
# Self-hosted; every course page lives four levels down: courses/<course>/<section>/<kind>/<page>.html
TO_ROOT = "../../../../"
PLOTLY_JS = TO_ROOT + "assets/js/plotly-2.35.2.min.js"
CALLOUT = {"hint": "tip", "tip": "tip", "note": "note", "important": "important",
           "warning": "warning", "caution": "caution", "info": "note"}
HINT_START = re.compile(r"^\s*(💡|\*\*(hints?|tip)\b|(hints?|tip)\s*:)", re.I)
# anchored at the start of a word so long base64 runs (Plotly data) stay linear-time
EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[a-z]{2,}")
PRIVACY = re.compile(r"(jedha|" + EMAIL_RE.pattern + r"|api[_-]?key\s*=\s*['\"][A-Za-z0-9]{12,}"
                     r"|bucket-jedha|hntran|huynam)", re.I)
DATA_RE = re.compile(r"""['"]((?:\.\./)?data/[^'"]+)['"]""")

log = []
_fig = [0]


# ---------- helpers ----------

def src(cell):
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else s


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def load(path):
    return json.load(open(path, encoding="utf-8"))


# ---------- markdown ----------

def convert_notes(text):
    def repl(m):
        kind = CALLOUT.get(m.group(1).strip().lower(), "note")
        return f"\n::: {{.callout-{kind}}}\n{m.group(2).strip()}\n:::\n"
    text = re.sub(r'<Note\s+type\s*=\s*"([^"]+)"\s*>(.*?)</Note>', repl, text, flags=re.S | re.I)

    # Docusaurus admonitions: ":::tip Optional title" ... ":::"
    def admonition(m):
        kind = CALLOUT.get(m.group(1).lower(), "note")
        title, body = (m.group(2) or "").strip(), (m.group(3) or "").strip()
        if not body:  # everything on the first line: it is the content, not a title
            title, body = "", title
        attrs = f".callout-{kind}" + (f' title="{title.replace(chr(34), chr(39))}"' if title else "")
        return f"\n\n::: {{{attrs}}}\n{body}\n:::\n\n"
    return re.sub(r"^[ \t]*:::[ \t]*([A-Za-z]+)[ \t]*([^\n]*)\n(?:(.*?)\n)?[ \t]*:::[ \t]*$", admonition, text,
                  flags=re.S | re.M)


def drop_blocked(text, where):
    out = []
    for line in text.split("\n"):
        low = line.lower()
        if any(h in low for h in BLOCKED_HOSTS):
            log.append(f"{where}: dropped line pointing to a blocked host: {line.strip()[:90]}")
            continue
        out.append(line)
    return "\n".join(out)


LIST_ITEM = re.compile(r"^\s{0,3}([-*+]|\d+[.)])\s+\S")


def blank_before_lists(text):
    """Jupyter renders a list right under a paragraph line; pandoc needs a blank line first."""
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if (not fence and LIST_ITEM.match(line) and out and out[-1].strip()
                and not LIST_ITEM.match(out[-1]) and not out[-1].startswith((" ", "\t", "|", ">"))):
            out.append("")
        out.append(line)
    return "\n".join(out)


def fold_hints(text):
    """Wrap hint paragraphs (💡…, **Hint:**, Tip:, …) in a collapsed 'Show hint' callout."""
    blocks, out = re.split(r"\n\s*\n", text), []
    for b in blocks:
        if HINT_START.match(b) and "Show hint" not in b:
            body = re.sub(r"^\s*💡\s*", "", b)
            out.append(f'::: {{.callout-tip collapse="true" title="Show hint"}}\n{body}\n:::')
        else:
            out.append(b)
    return "\n\n".join(out)


def heading_levels(cells):
    levels = []
    for c in cells:
        if c["cell_type"] != "markdown":
            continue
        fence = False
        for line in src(c).split("\n"):
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^(#{1,6})\s", line)
            if m:
                levels.append(len(m.group(1)))
    return levels


def shift_all(cells, top_level):
    levels = heading_levels(cells)
    shift = (top_level - min(levels)) if levels else 0
    for c in cells:
        if c["cell_type"] != "markdown" or not shift:
            continue
        out, fence = [], False
        for line in src(c).split("\n"):
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^(#{1,6})(\s+.*)$", line)
            if m:
                line = "#" * min(6, max(1, len(m.group(1)) + shift)) + m.group(2)
            out.append(line)
        c["source"] = "\n".join(out)
    return cells


def copy_local_images(text, nb_path, img_dir, img_rel):
    def fix(path):
        if re.match(r"^(https?:|data:|attachment:)", path):
            return path
        source = (nb_path.parent / path).resolve()
        if not source.exists():
            log.append(f"BROKEN image {path} in {nb_path.name}")
            return path
        img_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, img_dir / source.name)
        return f"{img_rel}/{source.name}"
    text = re.sub(r"(!\[[^\]]*\]\()([^)\s]+)", lambda m: m.group(1) + fix(m.group(2)), text)
    return re.sub(r'(<img[^>]*\bsrc\s*=\s*")([^"]+)', lambda m: m.group(1) + fix(m.group(2)), text)


# ---------- outputs ----------

def plotly_to_html(o):
    """Replace a saved Plotly figure (JSON) with HTML that draws it from the saved data."""
    fig = o["data"]["application/vnd.plotly.v1+json"]
    _fig[0] += 1
    div = f"sbfig{_fig[0]}"
    fig_out = {"data": fig.get("data", []), "layout": fig.get("layout", {})}
    if fig.get("frames"):
        fig_out["frames"] = fig["frames"]  # animations
    payload = json.dumps(fig_out, ensure_ascii=False).replace("</", "<\\/")
    html = (f'<div id="{div}" class="sb-plotly" style="width:100%;min-height:420px"></div>\n'
            f'<script>(function(){{var f={payload};f.layout.autosize=true;delete f.layout.width;'
            f'f.config={{responsive:true,displaylogo:false}};Plotly.newPlot("{div}",f);}})();</script>')
    return {"output_type": "display_data", "metadata": {"sb_plotly": True}, "data": {"text/html": html}}


def shorten(text, where):
    lines = text.split("\n")
    if len(lines) <= MAX_TEXT_LINES:
        return text
    log.append(f"{where}: shortened an output of {len(lines)} lines")
    return "\n".join(lines[:MAX_TEXT_LINES] + [f"… ({len(lines) - MAX_TEXT_LINES} more lines)"])


def clean_outputs(cell, where):
    outs = []
    for o in cell.get("outputs", []):
        if "application/vnd.plotly.v1+json" in o.get("data", {}):
            o = plotly_to_html(o)
        if EMAIL_RE.search(json.dumps(o)):
            log.append(f"{where}: dropped an output containing email addresses")
            continue
        data = o.get("data", {})
        if "text/html" in data and not o.get("metadata", {}).get("sb_plotly"):
            h = src({"source": data["text/html"]})
            if len(h) > MAX_HTML_BYTES:
                log.append(f"{where}: dropped an oversized HTML output ({len(h)//1024} KB)")
                continue
        if "text/plain" in data:
            data["text/plain"] = shorten(src({"source": data["text/plain"]}), where)
        if o.get("output_type") == "stream":
            o["text"] = shorten(src({"source": o["text"]}), where)
        o.pop("execution_count", None) if o.get("output_type") != "execute_result" else o.update(execution_count=None)
        outs.append(o)
    cell["outputs"], cell["execution_count"] = outs, None


# ---------- notebooks ----------

def prepare(cells, nb_path, where, img_dir, img_rel, top_level=None, hints=False):
    cells = [copy.deepcopy(c) for c in cells]
    for c in cells:
        c["metadata"] = {}
        c.pop("id", None)
        if c["cell_type"] == "markdown":
            t = drop_blocked(convert_notes(src(c)), where)
            t = copy_local_images(t, nb_path, img_dir, img_rel)
            t = blank_before_lists(t)
            if sum(1 for l in t.split("\n") if l.lstrip().startswith("```")) % 2:
                t = t.rstrip("\n") + "\n```"
                log.append(f"{where}: closed an unclosed code block in {nb_path.name}")
            c["source"] = fold_hints(t) if hints else t
        elif c["cell_type"] == "code":
            clean_outputs(c, where)
    cells = [c for c in cells if not (c["cell_type"] == "markdown" and not src(c).strip())]
    return shift_all(cells, top_level) if top_level else cells


def drop_title(cells):
    """Remove the notebook's own title: its first heading, only if it is a level-1 heading
    in the original notebook (the page has its own title). Notebooks without a title keep
    their first heading."""
    for i, c in enumerate(cells):
        if c["cell_type"] == "markdown" and src(c).strip():
            lines = src(c).split("\n")
            if re.match(r"^#\s", lines[0]):
                rest = "\n".join(lines[1:]).strip()
                return cells[:i] + ([md(rest)] if rest else []) + cells[i + 1:]
            return cells
    return cells


def slugify(text):
    text = re.sub(r"\{#[^}]*\}", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "section"


def exercise_level(cells):
    """The heading level that splits a notebook into exercises: the most frequent one (ties: the larger)."""
    from collections import Counter
    counts = Counter(heading_levels(cells))
    if not counts:
        return None
    top = max(counts.values())
    return min(l for l, c in counts.items() if c == top)


def add_heading_ids(cells, level=2, prefix="ex-"):
    """Give every heading of `level` an explicit id (same text -> same id on both pages)."""
    seen, ids = {}, []
    for c in cells:
        if c["cell_type"] != "markdown":
            continue
        out, fence = [], False
        for line in src(c).split("\n"):
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^(#{%d})\s+(.*?)\s*$" % level, line)
            if m and "{#" not in m.group(2):
                base = prefix + slugify(m.group(2))
                seen[base] = seen.get(base, 0) + 1
                hid = base if seen[base] == 1 else f"{base}-{seen[base]}"
                ids.append(hid)
                line = f"{m.group(1)} {m.group(2)} {{#{hid}}}"
            out.append(line)
        c["source"] = "\n".join(out)
    return cells, ids


def add_solution_links(cells, solution_page, solution_ids, level=2):
    """After each exercise block (a heading of `level`), link to the same block on the solutions page."""
    out, current = [], None
    def link():
        if current and current in solution_ids:
            out.append(md(f"[Solution →]({solution_page}#{current}){{.sb-sol-link}}"))
    for c in cells:
        if c["cell_type"] == "markdown":
            m = re.search(r"^#{%d}\s+.*\{#([^}]+)\}" % level, src(c), re.M)
            if m:
                link()
                current = m.group(1)
        out.append(c)
    link()
    return out


def front_matter(title, description, subtitle):
    return {"cell_type": "raw", "metadata": {}, "source": (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        f"subtitle: {json.dumps(subtitle, ensure_ascii=False)}\n"
        "include-in-header:\n"
        "  text: |\n"
        "    <script>window.__sbDefine = window.define; window.define = undefined;</script>\n"
        f"    <script src=\"{PLOTLY_JS}\" charset=\"utf-8\"></script>\n"
        "    <script>window.define = window.__sbDefine;</script>\n"
        "---")}


def write_nb(path, cells):
    nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}}
    for c in nb["cells"]:
        c["source"] = src(c).splitlines(keepends=True)
        c.setdefault("metadata", {})
        if c["cell_type"] == "code":
            c.setdefault("outputs", [])
            c.setdefault("execution_count", None)
            for o in c["outputs"]:
                if o.get("output_type") == "stream":
                    o["text"] = src({"source": o["text"]}).splitlines(keepends=True)
                for k, v in o.get("data", {}).items():
                    if isinstance(v, str) and k.startswith("text/"):
                        o["data"][k] = v.splitlines(keepends=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(nb, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def student_copy(nb_path, name, img_dir):
    """Lesson / exercise notebook as learners download it: the repo notebook unchanged,
    except image paths (-> ./img) and metadata. Outputs are kept as saved in the repo."""
    cells = copy.deepcopy(load(nb_path)["cells"])
    for c in cells:
        c["metadata"] = {}
        if c["cell_type"] == "markdown":
            c["source"] = copy_local_images(src(c), nb_path, img_dir, "img")
        c["source"] = src(c).splitlines(keepends=True)
    return json.dumps({"cells": cells, "nbformat": 4, "nbformat_minor": 5,
                       "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                   "name": "python3"}}}, ensure_ascii=False, indent=1)


MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".svg": "image/svg+xml", ".webp": "image/webp"}


def notebook_assets(nb_path):
    """What a notebook needs next to it: data files (../data/...), files it opens by bare name,
    and local helper modules it imports. Returns (data, siblings, helpers) as lists of Paths;
    data items are (absolute path, path relative to the data folder)."""
    code = "\n".join(src(c) for c in load(nb_path)["cells"] if c["cell_type"] == "code")
    data = []
    for d in sorted(set(DATA_RE.findall(code))):
        f = (nb_path.parent / d).resolve()
        data_root = (nb_path.parent / ("../data" if d.startswith("../") else "data")).resolve()
        if f.exists():
            data.append((f, f.relative_to(data_root)))
        else:
            log.append(f"BROKEN data file {d} in {nb_path.name}")
    siblings = sorted({nb_path.parent / n for n in re.findall(r"""["']([\w.-]+\.(?:csv|json|txt|xlsx))["']""", code)
                       if (nb_path.parent / n).exists()})
    helpers = sorted({nb_path.parent / f"{m}.py" for m in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", code, re.M)
                      if (nb_path.parent / f"{m}.py").exists()})
    return data, siblings, helpers


def embed_images(text, nb_path):
    """Replace local image paths by data: URIs so a downloaded notebook shows its images anywhere."""
    def inline(path):
        if re.match(r"^(https?:|data:|attachment:)", path):
            return path
        f = (nb_path.parent / path).resolve()
        if not f.exists() or f.suffix.lower() not in MIME:
            return path
        return f"data:{MIME[f.suffix.lower()]};base64," + base64.b64encode(f.read_bytes()).decode()
    text = re.sub(r"(!\[[^\]]*\]\()([^)\s]+)", lambda m: m.group(1) + inline(m.group(2)), text)
    return re.sub(r'(<img[^>]*\bsrc\s*=\s*")([^"]+)', lambda m: m.group(1) + inline(m.group(2)), text)


def download_copy(nb_path):
    """The notebook as learners download it: repo content and outputs, images embedded,
    data read from a `data` folder next to the notebook."""
    cells = copy.deepcopy(load(nb_path)["cells"])
    for c in cells:
        c["metadata"] = {}
        c.pop("id", None)
        t = src(c).replace("../data/", "data/")
        if c["cell_type"] == "markdown":
            t = embed_images(t, nb_path)
        c["source"] = t.splitlines(keepends=True)
    return json.dumps({"cells": cells, "nbformat": 4, "nbformat_minor": 5,
                       "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                   "name": "python3"}}}, ensure_ascii=False, indent=1)


def publish_downloads(sdir, nb_path, filename, also_from=None):
    """Write the downloadable notebook and its files into <section>/downloads/; return the header block.
    `also_from`: another notebook whose files are needed too (an exercise needs what its solution loads)."""
    ddir = sdir / "downloads"
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / filename).write_text(download_copy(nb_path), encoding="utf-8")
    data, siblings, helpers = notebook_assets(nb_path)
    if also_from is not None:
        d2, s2, h2 = notebook_assets(also_from)
        data = sorted(set(data) | set(d2), key=lambda x: str(x[1]))
        siblings, helpers = sorted(set(siblings) | set(s2)), sorted(set(helpers) | set(h2))
    for f, rel in data:
        (ddir / "data" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, ddir / "data" / rel)
    for f in siblings + helpers:
        shutil.copy2(f, ddir / f.name)
    items = [f"[Download this notebook](../downloads/{filename}){{download=\"{filename}\"}}"]
    if data:
        items.append("Data: " + " · ".join(f"[{rel.as_posix()}](../downloads/data/{rel.as_posix()}){{download=\"{rel.name}\"}}"
                                            for _, rel in data))
    if siblings + helpers:
        items.append("Also needed: " + " · ".join(f"[{f.name}](../downloads/{f.name}){{download=\"{f.name}\"}}"
                                                   for f in siblings + helpers))
    note = ("\n\nPut the data files in a folder named `data` next to the notebook"
            + (", and the other files next to the notebook." if siblings + helpers else ".")) if data else (
            "\n\nPut these files next to the notebook." if siblings + helpers else "")
    return "::: {.sb-downloads}\n" + "  \n".join(items) + note + "\n:::"


def parse_quiz(path):
    """Read a quiz file: '## question', '- [ ]' / '- [x]' options, '> explanation'."""
    title, questions, cur = None, [], None
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    for line in text.splitlines():
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.startswith("## "):
            cur = {"q": line[3:].strip(), "options": [], "answer": None, "explain": []}
            questions.append(cur)
        elif cur is not None and re.match(r"^- \[( |x|X)\] ", line):
            if line[3].lower() == "x":
                if cur["answer"] is not None:
                    log.append(f"BROKEN quiz {path.name}: two right answers in '{cur['q'][:50]}'")
                cur["answer"] = len(cur["options"])
            cur["options"].append(line[6:].strip())
        elif cur is not None and line.startswith(">"):
            cur["explain"].append(line[1:].strip())
    for q in questions:
        if q["answer"] is None or len(q["options"]) < 2:
            log.append(f"BROKEN quiz {path.name}: no right answer or fewer than 2 options in '{q['q'][:50]}'")
    return title, questions


def write_quiz(sdir, sec, course, n, quiz_path, lesson_href, next_link):
    title, questions = parse_quiz(quiz_path)
    body = ["---", f"title: {json.dumps(sec['title'] + ': quiz', ensure_ascii=False)}",
            f"subtitle: {json.dumps(course['title'] + f' · Section {n} · Quiz', ensure_ascii=False)}",
            f"description: {json.dumps('Check what you learned: ' + sec['description'], ensure_ascii=False)}",
            "include-after-body:", f"  text: '<script src=\"{TO_ROOT}assets/js/quiz.js\"></script>'", "---", "",
            links_block(("← Lesson", lesson_href)), "",
            f"{len(questions)} questions. Click an answer to check it: you will see right away whether it is "
            "correct, with a short explanation. Nothing is saved.", ""]
    for i, q in enumerate(questions, 1):
        body += [f'::: {{.sb-quiz-q data-answer="{q["answer"]}"}}', f"**{i}.** {q['q']}", "",
                 "::: {.sb-quiz-options}"] + [f"- {o}" for o in q["options"]] + [":::", "",
                 "::: {.sb-quiz-explain}", " ".join(q["explain"]), ":::", ":::", ""]
    body += ["::: {.sb-quiz-score}", ":::", ""]
    if next_link:
        body += [f"::: {{.sb-next}}\n**[{next_link[1]}]({next_link[0]})**\n:::", ""]
    out = sdir / "quiz" / "quiz.qmd"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(body), encoding="utf-8")
    return len(questions)


# ---------- build ----------

def section_plan(course):
    """Pages of every section: [(n, sec, name, lessons, exercises)] with resolved slugs and titles."""
    plan = []
    for n, sec in enumerate(course["sections"], 1):
        name = f"{n:02d}-{sec['slug']}"
        lessons = [dict(slug=l.get("slug", sec["slug"]), title=l.get("title", sec["title"]), path=l["path"])
                   for l in sec["lessons"]]
        plan.append((n, sec, name, lessons, sec.get("exercises", [])))
    return plan


TIME_HEADING = re.compile(r"^[ \t]*#+[ \t]*Time[ \t]*:[ \t]*([^\n{]+?)[ \t]*(\{[^}]*\})?[ \t]*$\n?", re.M | re.I)


def pop_time(cells):
    """Remove a 'Time : 15 min' heading from the notebook and return its duration ('15 min')."""
    found = None
    for c in cells:
        if c["cell_type"] == "markdown":
            m = TIME_HEADING.search(src(c))
            if m:
                found = found or m.group(1).strip()
                c["source"] = TIME_HEADING.sub("", src(c)).lstrip("\n")
    return [c for c in cells if c["cell_type"] != "markdown" or src(c).strip()], found


def links_block(*items):
    return "::: {.sb-lesson-links}\n" + "\n".join(f"[{t}]({h})" for t, h in items if h) + "\n:::"


def build_course(key, course, repo):
    out_dir = SITE / "courses" / key
    for old in list(out_dir.glob("[0-9][0-9]-*")) + [out_dir / "img", out_dir / "files"]:  # incl. quiz/
        shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink(missing_ok=True)
    plan = section_plan(course)
    link_checks = []
    for n, sec, name, lessons, exercises in plan:
        sdir = out_dir / name
        img_dir = sdir / "img"
        zip_href = f"../../files/{name}.zip"
        solution_only = bool(exercises) and "exercise" not in exercises[0]
        first_ex = (f"../{'solutions' if solution_only else 'exercises'}/{exercises[0]['slug']}.ipynb"
                    if exercises else None)
        ex_word = "solution" if solution_only else "exercises"
        quiz_src = repo / sec["quiz"] if sec.get("quiz") else None
        if quiz_src is not None and not quiz_src.exists():
            log.append(f"BROKEN quiz file {sec['quiz']}"); quiz_src = None
        quiz_href = "../quiz/quiz.qmd" if quiz_src else None
        multi_l, multi_e = len(lessons) > 1, len(exercises) > 1

        # lessons
        for k, les in enumerate(lessons):
            path = repo / les["path"]
            cells = prepare(load(path)["cells"], path, name, img_dir, "../img")
            cells = shift_all(drop_title(cells), top_level=2)
            nxt = (f"../lessons/{lessons[k + 1]['slug']}.ipynb", f"Next: {lessons[k + 1]['title']} →") if k + 1 < len(lessons) \
                else ((first_ex, f"Your turn: {sec['title']} {ex_word} →") if exercises else
                      ((quiz_href, f"Your turn: {sec['title']} quiz →") if quiz_href else (None, None)))
            title = les["title"] if multi_l else sec["title"]
            sub = f"{course['title']} · Section {n} · Lesson" + (f" {k + 1} of {len(lessons)}" if multi_l else "")
            tail = [md(f"::: {{.sb-next}}\n**[{nxt[1]}]({nxt[0]})**\n:::")] if nxt[0] else []
            dl = publish_downloads(sdir, path, f"lesson-{les['slug']}.ipynb")
            write_nb(sdir / "lessons" / f"{les['slug']}.ipynb",
                     [front_matter(title, sec["description"], sub),
                      md(links_block((f"{ex_word.capitalize()} →", first_ex), ("Quiz →", quiz_href), ("All files of this section (zip)", zip_href))),
                      md(dl)]
                     + cells + tail)

        if quiz_src:
            nq = write_quiz(sdir, sec, course, n, quiz_src, f"../lessons/{lessons[0]['slug']}.ipynb",
                            (first_ex, f"Next: {sec['title']} {ex_word} →") if first_ex else None)
            log.append(f"{name}: quiz with {nq} questions")

        # exercises and solutions (separate pages)
        for k, ex in enumerate(exercises):
            sol_path = repo / ex["solution"]
            sol_page = f"../solutions/{ex['slug']}.ipynb"
            sol_cells = prepare(load(sol_path)["cells"], sol_path, name, img_dir, "../img", hints=True)
            sol_cells = shift_all(drop_title(sol_cells), top_level=2)
            if "exercise" not in ex:  # project: the brief is the lesson, then one solution page
                write_nb(sdir / "solutions" / f"{ex['slug']}.ipynb",
                         [front_matter(f"{sec['title']}: a solution", f"A solution: {sec['description']}",
                                       f"{course['title']} · Section {n} · Solution"),
                          md(publish_downloads(sdir, sol_path, f"solution-{ex['slug']}.ipynb")),
                          md(links_block(("← Back to the project", f"../lessons/{lessons[0]['slug']}.ipynb"))
                             + "\n\n::: {.callout-tip}\nWork on the project on your own first: "
                               "you learn much more by searching than by reading a solution.\n:::")]
                         + sol_cells)
                continue
            ex_path = repo / ex["exercise"]
            ex_cells = prepare(load(ex_path)["cells"], ex_path, name, img_dir, "../img", hints=True)
            ex_cells, duration = pop_time(shift_all(drop_title(ex_cells), top_level=2))
            sol_cells, _ = pop_time(sol_cells)
            level = exercise_level(ex_cells)
            sol_ids = []
            if level:
                sol_cells, sol_ids = add_heading_ids(sol_cells, level)
                ex_cells, _ = add_heading_ids(ex_cells, level)
                ex_cells = add_solution_links(ex_cells, sol_page, set(sol_ids), level)
            if not any("sb-sol-link" in src(c) for c in ex_cells):
                ex_cells.append(md(f"[See the solutions →]({sol_page}){{.sb-sol-link}}"))
            link_checks += [(sdir / "solutions" / f"{ex['slug']}.ipynb", hid)
                            for hid in re.findall(r"\]\([^)#]*#([^)]+)\)\{\.sb-sol-link\}", "".join(src(c) for c in ex_cells))]
            title = f"{sec['title']}: exercises" if not multi_e else f"Exercises: {ex['title']}"
            sub = f"{course['title']} · Section {n} · Exercises" + (f" {k + 1} of {len(exercises)}" if multi_e else "") \
                + (f" · {duration}" if duration else "")
            nxt = [md(f"::: {{.sb-next}}\n**[Next exercises: {exercises[k + 1]['title']} →](../exercises/{exercises[k + 1]['slug']}.ipynb)**\n:::")] \
                if k + 1 < len(exercises) else []
            write_nb(sdir / "exercises" / f"{ex['slug']}.ipynb",
                     [front_matter(title, f"Exercises with hints: {sec['description']}", sub),
                      md(publish_downloads(sdir, ex_path, f"exercises-{ex['slug']}.ipynb", also_from=sol_path)),
                      md(links_block(("← Lesson", f"../lessons/{lessons[0]['slug']}.ipynb"), ("Solutions →", sol_page),
                                     ("All files of this section (zip)", zip_href))
                         + "\n\nTry each exercise on your own first. Stuck? Open a **hint**. "
                           "Done? Compare with the **solution** at the end of each exercise.")]
                     + ex_cells + nxt)
            stitle = f"{sec['title']}: solutions" if not multi_e else f"Solutions: {ex['title']}"
            write_nb(sdir / "solutions" / f"{ex['slug']}.ipynb",
                     [front_matter(stitle, f"Solutions: {sec['description']}",
                                   f"{course['title']} · Section {n} · Solutions"),
                      md(publish_downloads(sdir, sol_path, f"solutions-{ex['slug']}.ipynb")),
                      md(links_block(("← Back to the exercises", f"../exercises/{ex['slug']}.ipynb"))
                         + "\n\n::: {.callout-tip}\nTry the exercises on your own first: "
                           "you learn much more by searching than by reading a solution.\n:::")]
                     + sol_cells)

        # download bundle: lessons + exercise notebooks + data + images. Never the solutions.
        zpath = out_dir / "files" / f"{name}.zip"
        zpath.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            # flat: the notebooks, their data/ folder and helper files, exactly like the page downloads
            ddir = sdir / "downloads"
            wanted = [f"lesson-{l['slug']}.ipynb" for l in lessons] + [f"exercises-{e['slug']}.ipynb" for e in exercises
                                                                       if "exercise" in e]
            for f in sorted(ddir.rglob("*")):
                if f.is_file() and (not f.name.endswith(".ipynb") or f.name in wanted):
                    z.write(f, f"{name}/{f.relative_to(ddir).as_posix()}")
        log.append(f"{name}: {len(lessons)} lesson(s), {len(exercises)} exercise page(s) + solutions, "
                   f"zip {zpath.stat().st_size // 1024} KB")

    # every "Solution →" link must point to an anchor that exists
    for page, hid in link_checks:
        if f"{{#{hid}}}" not in page.read_text(encoding="utf-8"):
            log.append(f"BROKEN solution anchor #{hid} in {page.relative_to(SITE)}")
    write_overview(key, course, plan)
    return out_dir


def write_overview(key, course, plan):
    lines = ["---", f"title: {json.dumps(course['title'])}", f"subtitle: {json.dumps(course['subtitle'])}",
             "body-classes: sb-course-overview",
             f"description: {json.dumps('Free ' + course['title'] + ' course: lessons, exercises with hints, and solutions.')}",
             "---", "", "<!-- Generated by tools/build_courses.py: edit the COURSES config there. -->", "",
             course["intro"], "",
             "Each section has a zip with the lessons, the exercises and the data, so you can run everything "
             "on your computer (Python 3 with Jupyter, or [Anaconda](https://www.anaconda.com/download)). "
             "Solutions stay on this site.", ""]
    part = None
    for n, sec, name, lessons, exercises in plan:
        if sec.get("part") and sec["part"] != part:
            part = sec["part"]
            lines += ["", f"## {part}", ""]
        links = [f"[{'Lesson' if len(lessons) == 1 else 'Lessons'}]({name}/lessons/{lessons[0]['slug']}.ipynb)"]
        if sec.get("quiz"):
            links.append(f"[Quiz]({name}/quiz/quiz.qmd)")
        if exercises and "exercise" in exercises[0]:
            links.append(f"[Exercises]({name}/exercises/{exercises[0]['slug']}.ipynb)")
        if exercises:
            links.append(f"[Solution{'s' if 'exercise' in exercises[0] else ''}]({name}/solutions/{exercises[0]['slug']}.ipynb)")
        lines.append(f"{n}. **{sec['title']}**: {sec['description']} " + " · ".join(links))
    (SITE / "courses" / key / "index.qmd").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sidebars():
    """Sidebar for every course that has been built (courses/<key>/index.qmd exists)."""
    out = ["# Generated by tools/build_courses.py — do not edit by hand.", "website:", "  sidebar:"]
    for key, course in COURSES.items():
        if not (SITE / "courses" / key / "index.qmd").exists():
            continue
        out += [f"    - id: {key}", f"      title: \"{course['number']} · {course['title']}\"",
                "      style: floating", "      contents:",
                "        - text: \"All courses\"", "          href: courses/index.qmd",
                "        - text: \"Overview\"", f"          href: courses/{key}/index.qmd"]
        part, ind = None, "        "
        for n, sec, name, lessons, exercises in section_plan(course):
            if sec.get("part") and sec["part"] != part:
                part = sec["part"]
                out += [f"        - section: \"{part}\"", "          contents:"]
                ind = "            "
            base = f"courses/{key}/{name}"
            out += [f"{ind}- section: \"{n}. {sec['title']}\"", f"{ind}  contents:"]
            i2 = ind + "    "
            def group(label, items):
                if len(items) == 1:
                    return [f"{i2}- text: \"{label}\"", f"{i2}  href: {items[0][1]}"]
                rows = [f"{i2}- section: \"{label}\"", f"{i2}  contents:"]
                for t, h in items:
                    rows += [f"{i2}    - text: {json.dumps(t, ensure_ascii=False)}", f"{i2}      href: {h}"]
                return rows
            out += group("Lesson" if len(lessons) == 1 else "Lessons",
                         [(l["title"], f"{base}/lessons/{l['slug']}.ipynb") for l in lessons])
            if sec.get("quiz"):
                out += [f"{i2}- text: \"Quiz\"", f"{i2}  href: {base}/quiz/quiz.qmd"]
            with_ex = [e for e in exercises if "exercise" in e]
            if with_ex:
                out += group("Exercises", [(e["title"], f"{base}/exercises/{e['slug']}.ipynb") for e in with_ex])
            if exercises:
                out += group("Solutions" if with_ex else "Solution",
                             [(e["title"], f"{base}/solutions/{e['slug']}.ipynb") for e in exercises])
    (SITE / "courses" / "_sidebars.yml").write_text("\n".join(out) + "\n", encoding="utf-8")


def privacy_scan(paths):
    problems = []
    for p in paths:
        if p.suffix == ".zip":
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.endswith((".ipynb", ".csv", ".json", ".txt", ".md")):
                        t = z.read(n).decode("utf-8", "ignore")
                        problems += [f"{p.name}:{n}: {m.group(0)}" for m in PRIVACY.finditer(t)]
        else:
            t = p.read_text(encoding="utf-8", errors="ignore")
            problems += [f"{p.name}: {m.group(0)}" for m in PRIVACY.finditer(t)]
    return problems


def main():
    args = sys.argv[1:]
    if not args or len(args) % 2 or any(k not in COURSES for k in args[::2]):
        sys.exit(__doc__)
    failed = False
    for key, repo in zip(args[::2], args[1::2]):
        log.clear()
        out = build_course(key, COURSES[key], Path(repo).resolve())
        print("\n".join(dict.fromkeys(log)))
        problems = privacy_scan(list(out.rglob("*.ipynb")) + list((out / "files").glob("*.zip")))
        broken = [l for l in log if l.startswith("BROKEN")]
        if problems:
            print("\nPRIVACY SCAN FAILED:\n  " + "\n  ".join(sorted(set(problems))))
        print(f"{key}: privacy scan {'FAILED' if problems else 'clean'}; solution links "
              f"{'BROKEN' if broken else 'ok'}.\n")
        failed |= bool(problems or broken)
    write_sidebars()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
