import os
import redis

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=6379,
    db=0,
    decode_responses=True
)

def test_redis():
    r.set("test:key", "hello world!")
    value = r.get("test:key")
    print("Got from Redis:", value)

if __name__ == "__main__":
    test_redis()