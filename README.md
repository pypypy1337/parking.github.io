# Parking Monitoring

Flask application for configuring cameras, parking spaces, marked parking zones, forbidden zones, and occupancy state stored in local JSON files.

## Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Open `http://127.0.0.1:5000`.

Runtime state is stored in `data/parking_state.json`. Every write is atomic and keeps recent backups in `data/backups/`.

## Test

```bash
python -m unittest discover -s tests -v
```

## Recognition

The app includes a lightweight YOLO adapter in `detector.py`. It works without vision packages installed and can load an Ultralytics-compatible YOLOv12 model when the runtime environment provides `ultralytics`, OpenCV/frame capture, and a model file configured through the UI.
