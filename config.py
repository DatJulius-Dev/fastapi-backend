import os
import cloudinary

cloudinary.config(
    cloud_name="dqiclelb9",
    api_key="396125479862722",
    api_secret="Mv7yV4JZtuJxbXKHxJkh97wgrsA",
    secure=True
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")

MODEL_PATH = os.path.join(ARTIFACTS_DIR, "recomart_model.keras")
EMBEDDING_PATH = os.path.join(ARTIFACTS_DIR, "item_embeddings.npy")
CONTENT_PATH = os.path.join(ARTIFACTS_DIR, "item_content_vectors.npy")
META_PATH = os.path.join(ARTIFACTS_DIR, "ecommerce_api_metadata.pkl")

KEY_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

REDIS_HOST = 'redis-19872.c253.us-central1-1.gce.cloud.redislabs.com'
REDIS_PORT = 19872
REDIS_PASSWORD = 'FrvINGhjFiOkgWCzltf3eXd0CvvzULPP'
REDIS_DB = 0
CACHE_TTL = 3600

SEQ_LEN = 10
CONTENT_DIM = 32
ITEM_COUNT = 200
USER_COUNT = 20