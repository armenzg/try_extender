import logging
import os
import redis
from rq import Worker, Queue, Connection
from mozci.utils import transfer

transfer.MEMORY_SAVING_MODE = True

LOG = logging.getLogger()
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s:\t %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S')


listen = ['high', 'default', 'low']

redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')

conn = redis.from_url(redis_url)


if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
