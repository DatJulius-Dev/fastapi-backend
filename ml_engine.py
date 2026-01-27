import os
import numpy as np
import pandas as pd
import tensorflow as tf
import logging
import warnings
import joblib
import time
from datetime import datetime

from keras.saving import register_keras_serializable 
from keras.layers import Layer, Embedding, Dense, LayerNormalization, MultiHeadAttention, Dropout, Input, GlobalAveragePooling1D
from keras.models import Model

from config import *
try:
    from database import db
except ImportError:
    db = None
    print("Warning: Database module not found.")

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
tf.get_logger().setLevel(logging.ERROR)
logging.getLogger('tensorflow').setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

@register_keras_serializable() 
class PositionalEncoding(Layer):
    def __init__(self, seq_len, dim, **kwargs):
        super().__init__(**kwargs)
        self.seq_len = seq_len
        self.dim = dim
        self.supports_masking = True
        pos = np.arange(seq_len)[:, np.newaxis]
        i = np.arange(dim)[np.newaxis, :]
        angle_rates = 1 / np.power(10000, (2 * (i//2)) / np.float32(dim))
        angle_rads = pos * angle_rates
        angle_rads[:, 0::2] = np.sin(angle_rads[:, 0::2])
        angle_rads[:, 1::2] = np.cos(angle_rads[:, 1::2])
        self.pos_encoding = tf.constant(angle_rads[np.newaxis, ...], dtype=tf.float32)

    def call(self, x):
        return x + self.pos_encoding[:, :tf.shape(x)[1], :]

    def get_config(self):
        config = super().get_config()
        config.update({"seq_len": self.seq_len, "dim": self.dim})
        return config

@register_keras_serializable()
class TransformerEncoder(Layer):
    def __init__(self, d_model, num_heads, dff, rate=0.1, **kwargs):
        super().__init__(**kwargs)
        self.supports_masking = True
        self.d_model = d_model
        self.num_heads = num_heads
        self.dff = dff
        self.rate = rate
        self.mha = MultiHeadAttention(num_heads, key_dim=d_model, dropout=rate)
        # Dùng tf.keras.Sequential chuẩn
        self.ffn = tf.keras.Sequential([Dense(dff, activation='relu'), Dense(d_model)])
        self.layernorm1 = LayerNormalization(epsilon=1e-6)
        self.layernorm2 = LayerNormalization(epsilon=1e-6)
        self.dropout1 = Dropout(rate)
        self.dropout2 = Dropout(rate)

    def call(self, x, training=None, mask=None):
        attn = self.mha(x, x, use_causal_mask=True, training=training)
        attn = self.dropout1(attn, training=training)
        out1 = self.layernorm1(x + attn)
        ffn = self.ffn(out1)
        ffn = self.dropout2(ffn, training=training)
        return self.layernorm2(out1 + ffn)

    def get_config(self):
        config = super().get_config()
        config.update({"d_model": self.d_model, "num_heads": self.num_heads, "dff": self.dff, "rate": self.rate})
        return config

class MLResources:
    def __init__(self):
        self.model = None
        self.nlp_model = None
        self.item_embeddings = None
        self.content_vectors = None
        self.id_to_title = {}

    def load_all(self):
        print("--- Loading AI Resources ---")
        
        # A. Load Model RecSys (Dùng tf.keras.models.load_model chuẩn)
        try:
            if os.path.exists(MODEL_PATH):
                self.model = tf.keras.models.load_model(
                    MODEL_PATH,
                    custom_objects={
                        "PositionalEncoding": PositionalEncoding,
                        "TransformerEncoder": TransformerEncoder
                    }
                )
                print("Model AI: Loaded successfully!")
            else:
                print(f"Model file not found at {MODEL_PATH}")
                self.model = None
        except Exception as e:
            print(f"Model Load Error: {e}")
            self.model = None

        # B. Load Chatbot NLP
        try:
            from sentence_transformers import SentenceTransformer
            if os.path.exists(EMBEDDING_PATH) and os.path.exists(CONTENT_PATH):
                self.item_embeddings = np.load(EMBEDDING_PATH)
                self.content_vectors = np.load(CONTENT_PATH)
                if os.path.exists(META_PATH):
                    meta = joblib.load(META_PATH)
                    self.id_to_title = meta.get('ID_TO_TITLE_MOCK', {})
                
                self.nlp_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("Chatbot Data: Loaded")
            else:
                print("Thiếu file data Chatbot (npy)")
        except ImportError:
            print("Chưa cài thư viện sentence-transformers")
        except Exception as e:
            print(f"Chatbot Load Error: {e}")

# Khởi tạo instance
ml_resources = MLResources()

# Hàm tiện ích tìm kiếm Vector
def find_similar_items(query_vec, vector_matrix, top_k=5):
    if vector_matrix is None: return []
    dot = np.dot(vector_matrix, query_vec)
    norm_a = np.linalg.norm(vector_matrix, axis=1)
    norm_b = np.linalg.norm(query_vec)
    scores = dot / (norm_a * norm_b + 1e-9)
    top_idx = scores.argsort()[-(top_k+1):][::-1] 
    
    results = []
    for idx in top_idx:
        if scores[idx] < 0.1: continue 
        results.append({
            "id": int(idx),
            "name": ml_resources.id_to_title.get(int(idx), f"Sản phẩm #{idx}"),
            "score": float(scores[idx])
        })
    return results[:top_k]

def train_model_process():
    print("\n" + "="*30)
    print("STARTING RETRAINING PROCESS")
    print("="*30)

    # --- Step 1: Fetch Data from DB ---
    interactions = []
    
    if db:
        print("Fetching data from Firestore...")
        try:
            users_docs = db.collection('users').stream()
            for user in users_docs:
                uid = user.id
                # Fetch interactions
                logs = db.collection('users').document(uid).collection('interactions').stream()
                for log in logs:
                    data = log.to_dict()
                    interactions.append({
                        'user_id': uid,
                        'product_id': data.get('product_id'),
                        'timestamp': data.get('timestamp', 0),
                        'type': data.get('type')
                    })
            print(f"Fetched {len(interactions)} interaction records.")
        except Exception as e:
            print(f"Error fetching data: {e}")
            return {"status": "error", "message": str(e)}
    else:
        print("Database connection missing. Using DUMMY data for testing.")
        # Generate dummy data
        for _ in range(100):
            interactions.append({
                'user_id': np.random.randint(0, 10),
                'product_id': np.random.randint(0, 50), # 50 products
                'timestamp': time.time(),
                'type': 'view'
            })

    if not interactions:
        print("No data found. Aborting training.")
        return {"status": "warning", "message": "No data to train"}

    df = pd.DataFrame(interactions)
    
    # --- Step 2: Preprocessing ---
    print("Preprocessing data...")
    
    # 2.1 Map Product IDs to Integer Indices (0 to N)
    unique_products = df['product_id'].unique()
    product_to_idx = {pid: i + 1 for i, pid in enumerate(unique_products)} # Start from 1 (0 is padding)
    idx_to_product = {i + 1: pid for i, pid in enumerate(unique_products)}
    
    # Save mapping for inference later
    df['product_idx'] = df['product_id'].map(product_to_idx)
    
    # 2.2 Create User Sequences (Session-based)
    # Group by User -> Sort by Time -> Get list of product indices
    sequences = df.sort_values('timestamp').groupby('user_id')['product_idx'].apply(list).tolist()
    
    # 2.3 Generate Training Pairs (X, y)
    MAX_SEQ_LEN = 10 # Context window size
    VOCAB_SIZE = len(unique_products) + 1 # +1 for padding
    
    X_train = []
    y_train = []
    
    for seq in sequences:
        # Sliding window to create samples
        for i in range(1, len(seq)):
            # Input: up to last MAX_SEQ_LEN items
            start_idx = max(0, i - MAX_SEQ_LEN)
            x_seq = seq[start_idx:i]
            y_target = seq[i]
            
            # Pad sequence
            pad_len = MAX_SEQ_LEN - len(x_seq)
            x_seq = [0] * pad_len + x_seq
            
            X_train.append(x_seq)
            y_train.append(y_target)
            
    X_train = np.array(X_train)
    y_train = np.array(y_train)
    
    print(f"Training data shape: X={X_train.shape}, y={y_train.shape}")
    print(f"Vocabulary size: {VOCAB_SIZE}")

    # --- Step 3: Build Model ---
    print("Building Model Architecture...")
    
    EMBED_DIM = 64
    NUM_HEADS = 4
    FF_DIM = 128
    
    inputs = Input(shape=(MAX_SEQ_LEN,))
    
    embedding_layer = Embedding(input_dim=VOCAB_SIZE, output_dim=EMBED_DIM)
    x = embedding_layer(inputs)
    
    x = PositionalEncoding(MAX_SEQ_LEN, EMBED_DIM)(x)
    
    x = TransformerEncoder(d_model=EMBED_DIM, num_heads=NUM_HEADS, dff=FF_DIM)(x)
    
    x = GlobalAveragePooling1D()(x)
    x = Dropout(0.1)(x)
    outputs = Dense(VOCAB_SIZE, activation='softmax')(x)
    
    model = Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    
    print("Training Model...")
    model.fit(X_train, y_train, batch_size=32, epochs=5, validation_split=0.1)
    
    print("Saving Artifacts...")
    
    if not os.path.exists(os.path.dirname(MODEL_PATH)):
        os.makedirs(os.path.dirname(MODEL_PATH))
    model.save(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    
    embeddings_matrix = embedding_layer.get_weights()[0]
    np.save(EMBEDDING_PATH, embeddings_matrix)
    print(f"Embeddings saved to {EMBEDDING_PATH}")
    
    id_to_title_map = {}
    
    if db:
        products_ref = db.collection('products').stream()
        real_names = {p.id: p.to_dict().get('name', 'Unknown') for p in products_ref}
        
        for idx, real_pid in idx_to_product.items():
            id_to_title_map[idx] = real_names.get(real_pid, f"Item {real_pid}")
    else:
        for idx, real_pid in idx_to_product.items():
            id_to_title_map[idx] = f"Product {real_pid}"

    metadata = {
        'product_to_idx': product_to_idx,
        'idx_to_product': idx_to_product,
        'id_to_title': id_to_title_map,
        'vocab_size': VOCAB_SIZE,
        'trained_at': str(datetime.now())
    }
    joblib.dump(metadata, META_PATH)
    print(f"Metadata saved to {META_PATH}")

    print("="*30)
    print("RETRAINING COMPLETE")
    print("="*30)
    
    return {"status": "success", "message": "Model retrained successfully", "vocab_size": VOCAB_SIZE}