"""
Regenerate golden_expected.json so it matches classifier.pt's actual predictions
on the saved golden TIFFs.

Run from repo root after committing classifier.pt:
    python tools/regenerate_golden_expected.py
"""
import json, os, re, hashlib
from pathlib import Path

import torch
import torch.nn as nn
from torchvision import transforms as T
from torchvision.models import convnext_tiny
from PIL import Image

BACKEND_ROOT = Path(__file__).parent.parent
CLASSIFIER_PT  = BACKEND_ROOT / 'app/classifier/models/classifier.pt'
MODEL_CARD     = BACKEND_ROOT / 'app/classifier/models/model_card.json'
CLASS_NAMES_F  = BACKEND_ROOT / 'app/classifier/models/class_names.json'
GOLDEN_DIR     = BACKEND_ROOT / 'tests/golden/fixtures/golden_images'
GOLDEN_JSON    = BACKEND_ROOT / 'tests/golden/fixtures/golden_expected.json'

NUM_CLASSES = 16
IMNET_MEAN  = [0.485, 0.456, 0.406]
IMNET_STD   = [0.229, 0.224, 0.225]
IMG_SIZE    = 224

def build_model():
    model = convnext_tiny(weights=None)  # architecture only, no download
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, NUM_CLASSES)
    return model

def sha256(path, chunk=1024*1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while c := f.read(chunk):
            h.update(c)
    return h.hexdigest()

def main():
    # Load class names.
    with open(CLASS_NAMES_F) as f:
        class_names = json.load(f)
    assert len(class_names) == NUM_CLASSES

    # Determine device. Use CPU + fp32 to match what the service will do.
    # (If your service ever runs on GPU/AMP, change this and the model_card to match.)
    device = torch.device('cpu')

    # Build + load.
    model = build_model().to(device)
    state = torch.load(CLASSIFIER_PT, map_location=device)
    model.load_state_dict(state)
    model.eval()

    # Same transform the training notebook used for eval.
    eval_tfm = T.Compose([
        T.Resize(256),
        T.CenterCrop(IMG_SIZE),
        T.Lambda(lambda im: im.convert('RGB')),
        T.ToTensor(),
        T.Normalize(IMNET_MEAN, IMNET_STD),
    ])

    # Read existing JSON to preserve metadata fields (pick_type, dataset_index, etc.).
    with open(GOLDEN_JSON) as f:
        old_entries = {e['filename']: e for e in json.load(f)}

    new_entries = []
    tif_files = sorted(GOLDEN_DIR.glob('*.tif'))
    assert len(tif_files) == 50, f'Expected 50 TIFFs, found {len(tif_files)}'

    with torch.no_grad():
        for tif_path in tif_files:
            img = Image.open(tif_path)
            x = eval_tfm(img).unsqueeze(0).to(device)
            logits = model(x)
            probs = torch.softmax(logits.float(), dim=1)[0].cpu().numpy()
            pred = int(probs.argmax())
            conf = float(probs[pred])

            # Parse expected_label from filename: NNNNNN_classname.tif.
            m = re.match(r'(\d+)_(.+)\.tif', tif_path.name)
            assert m, f'Unexpected filename: {tif_path.name}'
            d_idx = int(m.group(1))
            true_class_from_name = m.group(2).replace('_', ' ')
            true_label = class_names.index(true_class_from_name)

            # Preserve old fields where useful.
            old = old_entries.get(tif_path.name, {})
            new_entries.append({
                'filename':                 tif_path.name,
                'dataset_index':            old.get('dataset_index', d_idx),
                'expected_label':           true_label,
                'expected_class':           true_class_from_name,
                'expected_top1_confidence': conf,
                'model_predicted_label':    pred,
                'model_predicted_class':    class_names[pred],
                'pick_type':                old.get('pick_type', 'unknown'),
            })

    # Atomic write.
    tmp = GOLDEN_JSON.with_suffix('.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(new_entries, f, indent=2)
    os.replace(tmp, GOLDEN_JSON)

    # Update SHA in model_card.json (in case classifier.pt changed since the card was written).
    with open(MODEL_CARD) as f:
        card = json.load(f)
    card['artifact']['sha256'] = sha256(CLASSIFIER_PT)
    card['artifact']['size_bytes'] = CLASSIFIER_PT.stat().st_size
    with open(MODEL_CARD, 'w') as f:
        json.dump(card, f, indent=2)

    print(f'Regenerated {GOLDEN_JSON} ({len(new_entries)} entries)')
    print(f'Updated SHA in {MODEL_CARD}: {card["artifact"]["sha256"][:12]}...')

if __name__ == '__main__':
    main()