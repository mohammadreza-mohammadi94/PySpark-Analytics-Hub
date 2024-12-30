# -*- coding: utf-8 -*-
"""DelayedFlightsPrediction.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1J49Vvye3h7TorHnPNqMkZuqt07aOTmf7

[Source](https://www.kaggle.com/datasets/patrickzel/flight-delay-and-cancellation-dataset-2019-2023)

# 1. Download Dataset
"""

!kaggle datasets download patrickzel/flight-delay-and-cancellation-dataset-2019-2023
!unzip /content/flight-delay-and-cancellation-dataset-2019-2023.zip

"""# 2. Import Libraries"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

from pyspark.sql import SparkSession
from pyspark.sql import functions as f
from pyspark.sql.types import *
from pyspark.ml.feature import (VectorAssembler,
                                StringIndexer,
                                StandardScaler,
                                OneHotEncoder)
from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.tuning import ParamGridBuilder, CrossValidator

"""# 3. Initializing Spark Session & Loading Dataset"""

# Starting Spark Session
spark = SparkSession.builder \
    .appName("FlightDelay") \
    .config('spark.driver.memory', '12g') \
    .config('spark.sql.shuffle.partitions', '8') \
    .config('spark.default.parallelism', '8') \
    .getOrCreate()

"""## 3.1 Loading Dataset"""

# Commented out IPython magic to ensure Python compatibility.
# %%time
# 
# # Load
# flights_df = (
#     spark.read.csv(
#         path="/content/flights_sample_3m.csv",
#         header=True,
#         inferSchema=True
#     )
# )
# 
# flights_df.cache()
# flights_df.count()

"""# 4. Analyzing & Preprocessing

## 4.1 Variable's Description

### 📆 **Date and Time Variables**
| **Variable**       | **Type**   | **Description**                                    |
|---------------------|-----------|----------------------------------------------------|
| **YEAR**           | Integer   | Year of the flight (e.g., 2019, 2020).             |
| **MONTH**          | Integer   | Month of the flight (1 = January, 12 = December).  |
| **DAY**            | Integer   | Day of the month.                                  |
| **DAY_OF_WEEK**    | Integer   | Day of the week (1 = Monday, 7 = Sunday).          |


### 🛫 **Flight Identification**
| **Variable**       | **Type**   | **Description**                                    |
|---------------------|-----------|----------------------------------------------------|
| **AIRLINE**        | String    | Airline code (e.g., AA for American Airlines).     |
| **FLIGHT_NUMBER**  | String    | Unique flight number assigned by the airline.     |
| **TAIL_NUMBER**    | String    | Aircraft registration number.                     |


### 🗺️ **Flight Route Information**
| **Variable**           | **Type**   | **Description**                                    |
|-------------------------|-----------|----------------------------------------------------|
| **ORIGIN_AIRPORT**      | String    | Origin airport code (e.g., JFK, LAX).             |
| **DESTINATION_AIRPORT** | String    | Destination airport code.                        |


### ⏱️ **Departure Details**
| **Variable**            | **Type**   | **Description**                                    |
|--------------------------|-----------|----------------------------------------------------|
| **SCHEDULED_DEPARTURE** | String    | Scheduled departure time (e.g., 14:30).           |
| **DEPARTURE_TIME**      | String    | Actual departure time.                            |
| **DEPARTURE_DELAY**     | Double    | Delay in minutes at departure. Positive if late.  |
| **TAXI_OUT**            | Double    | Time in minutes spent taxiing before takeoff.     |
| **WHEELS_OFF**          | String    | Time when the wheels left the ground.             |


### 🛬 **Arrival Details**
| **Variable**           | **Type**   | **Description**                                    |
|-------------------------|-----------|----------------------------------------------------|
| **SCHEDULED_ARRIVAL**  | String    | Scheduled arrival time.                           |
| **ARRIVAL_TIME**       | String    | Actual arrival time.                              |
| **ARRIVAL_DELAY**      | Double    | Delay in minutes at arrival. Positive if late.    |
| **TAXI_IN**            | Double    | Time in minutes spent taxiing after landing.      |
| **WHEELS_ON**          | String    | Time when the wheels touched the ground.          |


### 📊 **Flight Duration and Distance**
| **Variable**        | **Type**   | **Description**                                    |
|----------------------|-----------|----------------------------------------------------|
| **SCHEDULED_TIME**  | Double    | Planned duration of the flight (in minutes).       |
| **ELAPSED_TIME**    | Double    | Actual flight duration (in minutes).              |
| **AIR_TIME**        | Double    | Time spent in the air (in minutes).               |
| **DISTANCE**        | Double    | Distance traveled (in miles).                     |


### 🚦 **Flight Status**
| **Variable**        | **Type**   | **Description**                                    |
|----------------------|-----------|----------------------------------------------------|
| **DIVERTED**        | Integer   | 1 if the flight was diverted, 0 otherwise.         |
| **CANCELLED**       | Integer   | 1 if the flight was cancelled, 0 otherwise.        |
| **CANCELLATION_REASON** | String | Reason for cancellation: A (Airline), B (Weather), C (NAS), D (Security). |


### 🕒 **Delay Causes**
| **Variable**            | **Type**   | **Description**                                    |
|--------------------------|-----------|----------------------------------------------------|
| **AIR_SYSTEM_DELAY**    | Double    | Delay due to air traffic control system issues.   |
| **SECURITY_DELAY**      | Double    | Delay caused by security measures.               |
| **AIRLINE_DELAY**       | Double    | Delay caused by airline operations or crew.      |
| **LATE_AIRCRAFT_DELAY** | Double    | Delay caused by the late arrival of the aircraft. |
| **WEATHER_DELAY**       | Double    | Delay caused by weather conditions.              |

## 4.2 Dataset Structure
"""

print(" Dimension:\n", flights_df.count(), len(flights_df.columns))

flights_df.show(5)

flights_df.printSchema()

"""## 4.3 Missing Values"""

def check_missing_values(df):
    print("Column's Missing Values: \n")
    for col in df.columns:
        nans = df.filter(f.col(col).isNull()).count()
        if nans > 0:
            print(f"{col}: {nans}")

check_missing_values(flights_df)

flights_df.where("ARR_TIME > 0.0").show(10)

"""## 4.4 Statistical Overview"""

# Commented out IPython magic to ensure Python compatibility.
# %%time
# flights_df.select("DEP_DELAY", "ARR_DELAY", "DISTANCE", "ELAPSED_TIME", "DELAY_DUE_LATE_AIRCRAFT",
#                   "DELAY_DUE_SECURITY", "DELAY_DUE_CARRIER", "CANCELLED") \
#       .summary("count", "mean", "stddev", "min", "max") \
#       .show()

"""## 4.5 Creating Target Variable"""

flights_df = (
    flights_df.withColumn(
    "Is_Delayed",
    f.when(f.col("DEP_DELAY") >= 5.0, 1.0).otherwise(0.0)
    )
)

flights_df.groupBy("Is_Delayed").count().show()

"""## 4.6 Feature Eng"""

apt_traffic = flights_df.groupBy("ORIGIN").agg(
    f.count("*").alias("Daily_Flights")
    )

flights_df = flights_df.join(apt_traffic, "ORIGIN")

# Creating Is_Busy_Apt
flights_df = flights_df.withColumn("Is_Busy_Apt",
                                   f.when(f.col("Daily_Flights")> 1000, 1).otherwise(0))

# Extract Month, Day, Year

flights_df = (
    flights_df.withColumn("Year", f.year(flights_df['FL_DATE']))
    .withColumn("Month", f.month(flights_df['FL_DATE']))
    .withColumn("Day", f.dayofmonth(flights_df['FL_DATE'])
    )
)

flights_df.show(2)

"""## 4.7 Selecting Relevant Features"""

# flights_df.columns
flights_df.show(1)

df = flights_df.select("Month", "Day", "DEP_TIME", "DEP_DELAY",
                       "AIRLINE_CODE", "Is_Busy_Apt",
                       "Is_Delayed")

# print(df.columns)
df.show()

"""# 5. Vectorization & Encoding"""

# Categorical and numerical variables
categorical_variables = ["AIRLINE_CODE"]
numerical_variables = ["Month", "Day", "Is_Busy_Apt", "AIRLINE_CODE_INDEXED"]
target_variable = "Is_Delayed"

# Convert categorical varibale to numeric
indexer = StringIndexer(
    inputCol="AIRLINE_CODE",
    outputCol="AIRLINE_CODE_INDEXED"
)

df = indexer.fit(df).transform(df)

df.show(1) # Check df

# Feature's vectorization
vectorizer = VectorAssembler(
    inputCols= numerical_variables,
    outputCol="features_vector"
)

data = vectorizer.transform(df)

# Define random forest classifier model
rf = RandomForestClassifier(
    featuresCol="features_vector",
    labelCol="Is_Delayed",
    numTrees=200,
    maxDepth=10
)

data.show() # Check data

"""# 6. Training & Testing"""

# Splitting Train/Test
train, test = data.randomSplit([0.8, 0.2], seed=42)

# Training
model = rf.fit(train)

# Prediction
predictions = model.transform(test)
# Check predictions
predictions.show()

"""## 6.1 Confusion Matrix"""

# Calculate additional metrics
tp = predictions.filter((f.col("prediction") == 1.0) & (f.col("Is_Delayed") == 1.0)).count()
fp = predictions.filter((f.col("prediction") == 1.0) & (f.col("Is_Delayed") == 0.0)).count()
fn = predictions.filter((f.col("prediction") == 0.0) & (f.col("Is_Delayed") == 1.0)).count()

# Avoid division by zero
precision = tp / (tp + fp) if (tp + fp) != 0 else 0
recall = tp / (tp + fn) if (tp + fn) != 0 else 0

# Print the results
print(f"Precision: {precision}")
print(f"Recall: {recall}")

"""## 6.2 Evaluation"""

# Evaluate model
evaluator = BinaryClassificationEvaluator(
    labelCol="Is_Delayed",
    rawPredictionCol="rawPrediction",
    metricName="areaUnderROC"
)

accuracy = evaluator.evaluate(predictions)

accuracy

rf = RandomForestClassifier(labelCol="Is_Delayed", featuresCol="features_vector")

# تعریف پارامترهایی که می‌خواهیم جستجو کنیم
paramGrid = (ParamGridBuilder()
             .addGrid(rf.numTrees, [50, 100, 200])  # تعداد درخت‌ها
             .addGrid(rf.maxDepth, [5, 10, 20])  # عمق درخت‌ها
             .addGrid(rf.maxBins, [32, 64, 128])  # تعداد سطل‌ها
             .build())

# استفاده از CrossValidator برای ارزیابی مدل
evaluator = BinaryClassificationEvaluator(labelCol="Is_Delayed")

crossval = CrossValidator(estimator=rf,
                          estimatorParamMaps=paramGrid,
                          evaluator=evaluator,
                          numFolds=3)

# مدل را روی داده‌ها آموزش می‌دهیم
cvModel = crossval.fit(train)

# پیش‌بینی بر اساس مدل به دست آمده
predictions = cvModel.transform(test)

# ارزیابی مدل
accuracy = evaluator.evaluate(predictions)
print(f"Model Accuracy: {accuracy}")

train.show()

