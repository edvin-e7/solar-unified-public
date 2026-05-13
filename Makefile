.PHONY: help venv install dev dev-android android-apk android-install build pack clean verify journal docker-build docker-up docker-down qa-manual qa-reminder ml-encoder ml-train ml-eval ml-bootstrap ml-test ml-moondream ml-bootstrap-labels

VENV := $(abspath backend/.venv)
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
UVI  := $(VENV)/bin/uvicorn

help:
	@echo "Solar Unified — dev commands"
	@echo "  make install       Install backend (venv) + frontend deps"
	@echo "  make dev           Run backend + frontend in dev mode"
	@echo "  make build         Build frontend (dist/) and backend wheel"
	@echo "  make pack          Package Electron desktop app (current OS)"
	@echo "  make pack-all      Package for Win + Mac + Linux"
	@echo ""
	@echo "  Android (ChromeOS ARC++):"
	@echo "  make dev-android   Like 'dev' but backend binds 0.0.0.0 so APK can reach it"
	@echo "  make android-apk   Build debug APK (Capacitor + gradle, JDK 21 required)"
	@echo "  make android-install  adb-install the debug APK onto ARC++"
	@echo "  make verify        Run all verification scripts"
	@echo "  make journal       Show learning journal summary"
	@echo ""
	@echo "  ML detection (DETECTION_BACKEND=ml|embed|gemini|auto):"
	@echo "  make ml-bootstrap  Install deps + download encoder + sanity-check"
	@echo "  make ml-encoder    Download frozen embed encoder (mobilenet ONNX)"
	@echo "  make ml-train      Train numpy logistic head from labels.jsonl + prospects.db"
	@echo "  make ml-eval       Run eval_detection.py against fixtures sample set"
	@echo "  make ml-test       Run detection_model spec tests (pytest)"
	@echo "  make ml-moondream  Pull Moondream vision model via Ollama (free LLM, ~1.5 GB)"
	@echo "  make ml-bootstrap-labels  Distill Moondream labels for the fixture address list"
	@echo ""
	@echo "  make docker-build  Build backend + frontend Docker images"
	@echo "  make docker-up     docker compose up -d"
	@echo "  make docker-down   docker compose down"
	@echo "  make clean         Remove build artefacts"

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip wheel setuptools >/dev/null

install: venv
	$(PIP) install -r backend/requirements.txt
	cd frontend && pnpm install --strict-peer-dependencies=false

dev:
	@echo "Starting backend:8000 + frontend:5173..."
	@($(UVI) backend/main:app --reload --port 8000 &) && \
	 (cd frontend && pnpm dev)

# Like `dev` but binds the backend to all interfaces so the ChromeOS
# ARC++ Android container (or any LAN device) can reach it. Use with the
# Android APK built by `make android-apk`. Backend exposes PII over LAN —
# only run on a trusted network.
CAP_CORS := https://localhost,http://localhost,capacitor://localhost,ionic://localhost
# Default Android dev: zero-API-spend (Ollama for text + vision, ARC-reachable
# CORS origins). Override individual vars on the command line if needed, e.g.:
#   make dev-android OLLAMA_TEXT_MODEL=llama3.2:3b
dev-android:
	@echo "Starting backend on 0.0.0.0:8000 (LLM_PROVIDER=ollama, DETECTION_BACKEND=moondream)..."
	@echo "Crostini IP visible to ARC++: $$(hostname -I | awk '{print $$1}')"
	@command -v ollama >/dev/null 2>&1 || { echo "WARN: ollama not found — pitch + detection will fail"; }
	@(cd backend && \
	  ALLOW_BOOT_WITHOUT_KEYS=$${ALLOW_BOOT_WITHOUT_KEYS:-1} \
	  CORS_ORIGINS="$(CAP_CORS),http://localhost:5173,http://127.0.0.1:5173" \
	  LLM_PROVIDER=$${LLM_PROVIDER:-ollama} \
	  DETECTION_BACKEND=$${DETECTION_BACKEND:-moondream} \
	  OLLAMA_TEXT_MODEL=$${OLLAMA_TEXT_MODEL:-qwen2.5:1.5b} \
	  OLLAMA_VISION_MODEL=$${OLLAMA_VISION_MODEL:-moondream} \
	  $(UVI) main:app --reload --host 0.0.0.0 --port 8000 &) && \
	 (cd frontend && pnpm dev)

# Backend-only variant for use with the installed APK (skip Vite).
serve-android:
	@echo "Starting backend on 0.0.0.0:8000 for the APK to consume..."
	@(cd backend && \
	  ALLOW_BOOT_WITHOUT_KEYS=$${ALLOW_BOOT_WITHOUT_KEYS:-1} \
	  CORS_ORIGINS="$(CAP_CORS),http://localhost:5173,http://127.0.0.1:5173" \
	  LLM_PROVIDER=$${LLM_PROVIDER:-ollama} \
	  DETECTION_BACKEND=$${DETECTION_BACKEND:-moondream} \
	  OLLAMA_TEXT_MODEL=$${OLLAMA_TEXT_MODEL:-qwen2.5:1.5b} \
	  OLLAMA_VISION_MODEL=$${OLLAMA_VISION_MODEL:-moondream} \
	  $(UVI) main:app --host 0.0.0.0 --port 8000)

# Build a debug Android APK that wraps the PWA and points at the Crostini
# backend. Requires JDK 21 + Android SDK + Capacitor (see scripts/android_env.sh).
# Output: frontend/android/app/build/outputs/apk/debug/app-debug.apk
android-apk:
	@. ~/.solar-android-env.sh && \
	 IP=$$(hostname -I | awk '{print $$1}') && \
	 echo "Crostini IP for VITE_API_URL: $$IP" && \
	 cd frontend && \
	 VITE_API_URL=http://$$IP:8000 pnpm build && \
	 pnpm exec cap sync android && \
	 cd android && ./gradlew assembleDebug
	@echo ""
	@echo "APK: frontend/android/app/build/outputs/apk/debug/app-debug.apk"
	@echo "Install with: make android-install"

# Install the debug APK onto the ChromeOS ARC++ Android container.
# Prerequisite: ChromeOS Settings → Linux → "Develop Android apps" toggle ON.
android-install:
	@. ~/.solar-android-env.sh && \
	 adb devices | grep -q '100.115.92.2:5555' || adb connect 100.115.92.2:5555 && \
	 adb -s 100.115.92.2:5555 install -r frontend/android/app/build/outputs/apk/debug/app-debug.apk

build:
	cd frontend && pnpm build

pack: build
	cd frontend && pnpm electron:pack:$(shell node -e "console.log({darwin:'mac',linux:'linux',win32:'win'}[process.platform])")

pack-all: build
	cd frontend && pnpm electron:pack:all

verify: qa-reminder
	$(PY) backend/scripts/verify_all.py

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

journal:
	@cat backend/prompts/learned/summary.md 2>/dev/null || echo "(no journal yet)"

clean:
	rm -rf frontend/dist frontend/release backend/__pycache__ backend/data/images backend/data/history
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

qa-manual:
	@echo "→ Run docs/QA_MANUAL.md end-to-end (~15 min)"
	@echo "→ When done, append a row to docs/QA_RUN_LOG.md"
	@head -10 docs/QA_MANUAL.md

qa-reminder:
	@echo ""
	@echo "Reminder: if you touched UI or API, run 'make qa-manual' before merging."
	@echo ""

ml-encoder: venv
	$(PY) backend/scripts/download_encoder.py

ml-train: venv
	$(PY) backend/scripts/auto_train_detection.py

ml-eval: venv
	$(PY) backend/scripts/eval_detection.py --addresses backend/scripts/fixtures/eval_set_sample.txt

ml-test: venv
	$(VENV)/bin/pytest backend/specs/test_detection_model.py -v

ml-moondream:
	@command -v ollama >/dev/null 2>&1 || { \
	  echo "Ollama not found. Install once with:"; \
	  echo "  curl -fsSL https://ollama.com/install.sh | sh"; \
	  echo "Then re-run 'make ml-moondream'."; exit 1; }
	ollama pull moondream
	@echo ""
	@echo "Moondream pulled. Use it via DETECTION_BACKEND=moondream."
	@echo "Make sure 'ollama serve' is running (default on linux/mac after install)."

ml-bootstrap-labels: venv
	$(PY) backend/scripts/bootstrap_labels.py \
	  --addresses backend/scripts/fixtures/bootstrap_addresses.txt \
	  --teacher moondream

ml-bootstrap: install ml-encoder
	@echo ""
	@echo "ML bootstrap done."
	@echo "Next:"
	@echo "  1. Set GOOGLE_MAPS_API_KEY + GEMINI_API_KEY in .env"
	@echo "  2. (optional) Drop YOLOv8-seg ONNX at backend/models/yolov8n-solar-seg.onnx"
	@echo "     to enable the 'ml' backend; otherwise 'embed' + 'gemini' are usable."
	@echo "  3. DETECTION_BACKEND=auto make ml-eval"
