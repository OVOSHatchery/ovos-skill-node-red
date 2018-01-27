from sqlalchemy import Column, Text, String, Integer, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from os.path import dirname, join


__author__ = "JarbasAI"


Base = declarative_base()


def model_to_dict(obj):
    serialized_data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
    return serialized_data


def props(cls):
    return [i for i in cls.__dict__.keys() if i[:1] != '_']


class NodeRedConnection(Base):
    __tablename__ = "nodes"
    id = Column(Integer, primary_key=True)
    description = Column(Text)
    api_key = Column(String)
    name = Column(String)
    mail = Column(String)
    last_seen = Column(Integer, default=0)


class NodeDatabase(object):
    def __init__(self, path=None, debug=False):
        path = path or join("sqlite:///",  dirname(__file__), "nodes.db")
        self.db = create_engine(path)
        self.db.echo = debug

        Session = sessionmaker(bind=self.db)
        self.session = Session()
        Base.metadata.create_all(self.db)

    def update_timestamp(self, api, timestamp):
        node = self.get_node_by_api_key(api)
        if not node:
            return False
        node.last_seen = timestamp
        return self.commit()

    def delete_node(self, api):
        node = self.get_node_by_api_key(api)
        if node:
            self.session.delete(node)
            return self.commit()
        return False

    def change_api(self, node_name, new_key):
        node = self.get_node_by_name(node_name)
        if not node:
            return False
        node.api_key = new_key
        return self.commit()

    def get_node_by_api_key(self, api_key):
        return self.session.query(NodeRedConnection).filter_by(api_key=api_key).first()

    def get_node_by_name(self, name):
        return self.session.query(NodeRedConnection).filter_by(name=name).first()

    def add_node(self, name=None, mail=None, api=""):
        node = NodeRedConnection(api_key=api, name=name, mail=mail,
                                 id=self.total_nodes() + 1)
        self.session.add(node)
        return self.commit()

    def total_nodes(self):
        return self.session.query(NodeRedConnection).count()

    def commit(self):
        try:
            self.session.commit()
            return True
        except IntegrityError:
            self.session.rollback()
        return False

if __name__ == "__main__":
    db = NodeDatabase(debug=True)
    name = "jarbas"
    mail = "jarbasai@mailfence.com"
    api = "admin_key"
    db.add_node(name, mail, api)


