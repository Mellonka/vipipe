from dataclasses import dataclass, field

import sqlalchemy
from vipipe.transport.interface import MultipartWriterABC


@dataclass
class PostgresWriterConfig:
    connection_string: str
    """Строка подключения к базе данных"""


@dataclass
class PostgresWriter(MultipartWriterABC[sqlalchemy.orm.DeclarativeBase]):
    config: PostgresWriterConfig

    engine: sqlalchemy.Engine = field(init=False)
    connection: sqlalchemy.Connection = field(init=False)

    def __post_init__(self):
        self.engine = sqlalchemy.create_engine(self.config.connection_string)
        self.connection = self.engine.connect()

    def write(self, message: sqlalchemy.orm.DeclarativeBase) -> None:
        self.connection.execute(sqlalchemy.insert(message.__table__), message)

    def write_multipart(self, message_parts: list[sqlalchemy.orm.DeclarativeBase]) -> None:
        if len(message_parts) == 0:
            return

        self.connection.execute(sqlalchemy.insert(message_parts[0].__table__), message_parts)
