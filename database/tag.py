from sqlalchemy import BigInteger, Column, Integer, String

from database.database import Base, get_engine


class Tag(Base):
    __tablename__ = 'admin_tag'

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    name = Column(String, nullable=False)
    message = Column(String, nullable=False)


if __name__ == '__main__':
    with get_engine(async_=False).begin() as engine:
        Base.metadata.create_all(bind=engine)
