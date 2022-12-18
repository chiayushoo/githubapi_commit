import airflow
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta

# default arguments for the DAG
default_args = {
    'owner': 'me',
    'start_date': datetime(2022, 12, 17),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# create a DAG with the default arguments
dag = DAG(
    'run_script_everyday',
    default_args=default_args,
    schedule_interval='0 0 * * *',  # run the DAG every day at midnight
    catchup=False
)

# define the function that will run the script


def run_script():
    import requests
    from requests import get
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    from pyspark.context import SparkContext
    from pyspark.sql.session import SparkSession
    from pyspark.sql import functions as F
    import mysql.connector
    from pyspark.sql.functions import *

    sc = SparkContext('local')
    spark = SparkSession(sc)

    # setup owner name , access_token, and headers
    owner = '{sealed_name}'
    access_token = '{sealed_taken}'
    headers = {'Authorization': "Token "+access_token}

    def get_commits_l6m(**kwargs):
        """
        Returns the commits to a GitHub repository.
        """
        biz_date = datetime.today() + relativedelta(months=-6)
        biz_date = biz_date.isoformat()
        params = {
            "since": biz_date,
            "per_page": 100,  # Number of results per page
            "page": 1  # Page number to retrieve
        }
        # initial request
        response = requests.get(
            'https://api.github.com/repos/apache/airflow/commits', params)

        if response.status_code == 200:
            results = response.json()
            # set a marker to see if we retrive all of the results
            done = False

            while not done:
                if 'next' in response.links:
                    params["page"] += 1
                    response = requests.get(
                        'https://api.github.com/repos/apache/airflow/commits', params)
                    if response.status_code == 200:
                        results.extend(response.json())
                    else:
                        # There was an error with the request, so stop processing
                        done = True
                else:
                    # There are no more pages of results, so stop processing
                    done = True
                    commit_data = [i["commit"]["author"] for i in results]
        columns = ["datetime", "email", "name"]
        df_commit = spark.createDataFrame(data=commit_data, schema=columns)
        df_commit = df_commit.withColumn(
            'grass_date', date_format(current_timestamp(), 'yyyy-MM-dd'))
        df_commit = df_commit.withColumn(
            "datetime", date_format('datetime', "yyyy-MM-dd HH:mm:ss"))

        # connect to mysql db
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='kelsy2022',
            database='edb'
        )
        # Create a cursor
        cursor = conn.cursor()

        # Insert the DataFrame data into the MySQL table
        for row in df_commit.rdd.toLocalIterator():
            insert_query = f"INSERT INTO commit_l6m_airflow VALUES ({','.join(['%s'] * len(row))})"
        conn.cursor().execute(insert_query, row)

        # Commit the changes
        conn.commit()
        # Close the cursor and connection
        cursor.close()
        conn.close()


# define the task that will run the script
run_script_task = PythonOperator(
    task_id='run_script',
    python_callable=get_commits_l6m,
    dag=dag
)

# add the task to the DAG
run_script_task.set_upstream(dag)
