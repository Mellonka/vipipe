from datetime import datetime

import sqlalchemy
from sqlalchemy.orm import DeclarativeBase
from vipipe.transport.postgres.writer import PostgresWriter, PostgresWriterConfig
from vipipe.transport.s3.writer import S3Object, S3Writer, S3WriterConfig


class SensorData(DeclarativeBase):
    __tablename__ = "sensor_data"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    timestamp = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    sensor_id = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    value = sqlalchemy.Column(sqlalchemy.Float, nullable=False)
    unit = sqlalchemy.Column(sqlalchemy.String, nullable=False)


def main():
    # Конфигурация PostgreSQL
    pg_config = PostgresWriterConfig(connection_string="postgresql://user:password@localhost:5432/mydb")

    # Конфигурация S3
    s3_config = S3WriterConfig(
        bucket_name="my-bucket", region_name="us-east-1", access_key="your-access-key", secret_key="your-secret-key"
    )

    # Создание экземпляров writer'ов
    pg_writer = PostgresWriter(config=pg_config)
    s3_writer = S3Writer(config=s3_config)

    with pg_writer, s3_writer:
        # Пример записи данных в PostgreSQL
        sensor_data = SensorData(timestamp=datetime.now(), sensor_id="SENSOR_001", value=25.5, unit="C")
        pg_writer.write(sensor_data)

        # Пример multipart записи в PostgreSQL
        sensor_data_list = [
            SensorData(timestamp=datetime.now(), sensor_id=f"SENSOR_{i:03d}", value=20.0 + i, unit="C")
            for i in range(3)
        ]
        pg_writer.write_multipart(sensor_data_list)

        # Пример записи файла в S3
        s3_object = S3Object(key="data/sensor_data.txt", message=b"Some sensor data content")
        s3_writer.write(s3_object)


if __name__ == "__main__":
    main()
