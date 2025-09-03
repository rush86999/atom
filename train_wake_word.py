# This script is based on the training scripts from the openWakeWord project.
# For more information, see: https://github.com/dscripka/openWakeWord
import os
import collections
import numpy as np
from numpy.lib.format import open_memmap
from pathlib import Path
from tqdm import tqdm
import openwakeword
import openwakeword.data
import openwakeword.utils
import openwakeword.metrics
import scipy
import datasets
import torch
from torch import nn
import tarfile
import zipfile
import librosa

# --- Configuration ---
POSITIVE_SAMPLES_DIR = "audio_samples"
NEGATIVE_SAMPLES_DIR = "negative_samples"
POSITIVE_FEATURES_FILE = "positive_features.npy"
NEGATIVE_FEATURES_FILE = "negative_features.npy"
MODEL_OUTPUT_FILE = "atom_wake_word.onnx"
VERIFIER_MODEL_OUTPUT_FILE = "atom_verifier.pkl"


def download_and_extract(url, target_dir):
    """Downloads and extracts a file."""
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    filename = url.split("/")[-1]
    filepath = os.path.join(target_dir, filename)
    if not os.path.exists(filepath):
        print(f"Downloading {url}...")
        os.system(f"wget {url} -O {filepath}")
    if filepath.endswith(".tar.gz"):
        with tarfile.open(filepath, "r:gz") as tar:
            tar.extractall(path=target_dir)
    elif filepath.endswith(".zip"):
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(target_dir)

def main():
    """
    Trains a new openWakeWord model for the wake word "Atom".
    """
    # --- Data Preparation ---
    print("--- Data Preparation ---")

    # Create negative samples directory
    if not os.path.exists(NEGATIVE_SAMPLES_DIR):
        os.makedirs(NEGATIVE_SAMPLES_DIR)

    # Download and extract negative samples (FSD50k)
    download_and_extract("https://f002.backblazeb2.com/file/openwakeword-resources/data/fsd50k_sample.zip", NEGATIVE_SAMPLES_DIR)

    # --- Feature Extraction ---
    print("--- Feature Extraction ---")

    # Create audio pre-processing object
    F = openwakeword.utils.AudioFeatures()

    # Get negative example paths
    negative_clips, negative_durations = openwakeword.data.filter_audio_paths(
        [os.path.join(NEGATIVE_SAMPLES_DIR, "fsd50k_sample")],
        min_length_secs=1.0,
        max_length_secs=60 * 30,
        duration_method="header"
    )
    print(f"{len(negative_clips)} negative clips after filtering, representing ~{sum(negative_durations)//3600} hours")

    # Get audio embeddings for negative clips
    audio_dataset = datasets.Dataset.from_dict({"audio": negative_clips})
    audio_dataset = audio_dataset.cast_column("audio", datasets.Audio(sampling_rate=16000))

    batch_size = 64
    clip_size = 3
    N_total = int(sum(negative_durations) // clip_size)
    n_feature_cols = F.get_embedding_shape(clip_size)

    output_array_shape = (N_total, n_feature_cols[0], n_feature_cols[1])
    fp = open_memmap(NEGATIVE_FEATURES_FILE, mode='w+', dtype=np.float32, shape=output_array_shape)

    row_counter = 0
    for i in tqdm(np.arange(0, audio_dataset.num_rows, batch_size)):
        wav_data = [(j["array"] * 32767).astype(np.int16) for j in audio_dataset[i:i + batch_size]["audio"]]
        wav_data = openwakeword.data.stack_clips(wav_data, clip_size=16000 * clip_size).astype(np.int16)
        features = F.embed_clips(x=wav_data, batch_size=1024, ncpu=8)
        if row_counter + features.shape[0] > N_total:
            fp[row_counter:min(row_counter + features.shape[0], N_total), :, :] = features[0:N_total - row_counter, :, :]
            fp.flush()
            break
        else:
            fp[row_counter:row_counter + features.shape[0], :, :] = features
            row_counter += features.shape[0]
            fp.flush()
    openwakeword.data.trim_mmap(NEGATIVE_FEATURES_FILE)

    # Get positive example paths
    positive_clips, durations = openwakeword.data.filter_audio_paths(
        [POSITIVE_SAMPLES_DIR],
        min_length_secs=0.1,
        max_length_secs=2.0,
        duration_method="header"
    )
    print(f"{len(positive_clips)} positive clips after filtering")

    # Get audio embeddings for positive clips
    sr = 16000
    total_length_seconds = 3
    total_length = int(sr * total_length_seconds)
    jitters = (np.random.uniform(0, 0.2, len(positive_clips)) * sr).astype(np.int32)
    starts = [total_length - (int(np.ceil(i * sr)) + j) for i, j in zip(durations, jitters)]
    mixing_generator = openwakeword.data.mix_clips_batch(
        foreground_clips=positive_clips,
        background_clips=negative_clips,
        combined_size=total_length,
        batch_size=batch_size,
        snr_low=5,
        snr_high=15,
        start_index=starts,
        volume_augmentation=True,
    )

    N_total = len(positive_clips)
    n_feature_cols = F.get_embedding_shape(total_length_seconds)
    output_array_shape = (N_total, n_feature_cols[0], n_feature_cols[1])
    fp = open_memmap(POSITIVE_FEATURES_FILE, mode='w+', dtype=np.float32, shape=output_array_shape)

    row_counter = 0
    for batch in tqdm(mixing_generator, total=N_total // batch_size):
        batch, lbls, background = batch[0], batch[1], batch[2]
        features = F.embed_clips(batch, batch_size=256)
        fp[row_counter:row_counter + features.shape[0], :, :] = features
        row_counter += features.shape[0]
        fp.flush()
        if row_counter >= N_total:
            break
    openwakeword.data.trim_mmap(POSITIVE_FEATURES_FILE)

    # --- Model Training ---
    print("--- Model Training ---")

    negative_features = np.load(NEGATIVE_FEATURES_FILE)
    positive_features = np.load(POSITIVE_FEATURES_FILE)

    X = np.vstack((negative_features, positive_features))
    y = np.array([0] * len(negative_features) + [1] * len(positive_features)).astype(np.float32)[..., None]

    batch_size = 512
    training_data = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.from_numpy(X), torch.from_numpy(y)),
        batch_size=batch_size,
        shuffle=True
    )

    layer_dim = 32
    fcn = nn.Sequential(
        nn.Flatten(),
        nn.Linear(X.shape[1] * X.shape[2], layer_dim),
        nn.LayerNorm(layer_dim),
        nn.ReLU(),
        nn.Linear(layer_dim, layer_dim),
        nn.LayerNorm(layer_dim),
        nn.ReLU(),
        nn.Linear(layer_dim, 1),
        nn.Sigmoid(),
    )

    loss_function = torch.nn.functional.binary_cross_entropy
    optimizer = torch.optim.Adam(fcn.parameters(), lr=0.001)

    n_epochs = 10
    for i in tqdm(range(n_epochs), total=n_epochs):
        for batch in training_data:
            x_batch, y_batch = batch[0], batch[1]
            weights = torch.ones(y_batch.shape[0])
            weights[y_batch.flatten() == 1] = 0.1
            optimizer.zero_grad()
            predictions = fcn(x_batch)
            loss = loss_function(predictions, y_batch, weights[..., None])
            loss.backward()
            optimizer.step()

    # --- Model Export ---
    print("--- Model Export ---")
    torch.onnx.export(fcn, args=torch.zeros((1, 28, 96)), f=MODEL_OUTPUT_FILE)

    # --- Verifier Model Training ---
    print("--- Verifier Model Training ---")
    openwakeword.train_custom_verifier(
        positive_reference_clips=positive_clips,
        negative_reference_clips=negative_clips,
        output_path=VERIFIER_MODEL_OUTPUT_FILE,
        model_name=MODEL_OUTPUT_FILE,
        threshold=0.0
    )

    print("--- Done! ---")
    print(f"Wake word model saved to: {MODEL_OUTPUT_FILE}")
    print(f"Verifier model saved to: {VERIFIER_MODEL_OUTPUT_FILE}")

if __name__ == "__main__":
    main()