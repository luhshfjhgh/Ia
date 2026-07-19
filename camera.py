# -*- coding: utf-8 -*-
"""
camera.py — NOX AI Vision Module
==================================
Deteccao de objetos, pessoas, animais e muito mais em tempo real.
Usa YOLOv8 (ultralytics) + OpenCV.

Instalacao das dependencias:
    pip install ultralytics opencv-python

Como funciona:
    - Ao ser ativado pelo botao VISION da interface, abre a camera
    - Detecta e rotula tudo que aparece na imagem em tempo real
    - Exibe caixas coloridas com nome e confianca de cada objeto
    - Reporta deteccoes para o log da interface NOX
    - Pressione Q ou feche a janela para encerrar

Integrado com voice_ui.py -> NoxWebApi.toggle_camera()
"""

import os
import sys
import time
import threading
import queue

# ── OpenCV ────────────────────────────────────────────────────────────────
try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False
    cv2 = None

# ── YOLOv8 ────────────────────────────────────────────────────────────────
try:
    from ultralytics import YOLO
    YOLO_OK = True
except ImportError:
    YOLO_OK = False
    YOLO = None

# ── Cores por categoria de objeto (BGR) ───────────────────────────────────
CATEGORY_COLORS = {
    "person":       (0,   200, 255),   # ciano
    "car":          (255, 100,   0),   # azul
    "truck":        (255,  60,   0),
    "bus":          (255,  80,  20),
    "motorcycle":   (200, 150,   0),
    "bicycle":      (180, 200,   0),
    "dog":          (0,   255, 120),   # verde
    "cat":          (0,   220, 100),
    "bird":         (0,   180, 255),
    "cell phone":   (180,   0, 255),   # roxo
    "laptop":       (160,   0, 255),
    "tv":           (140,   0, 255),
    "chair":        (100, 100, 100),   # cinza
    "default":      (255, 210, 122),   # dourado NOX
}

# Traducao para portugues dos labels mais comuns do COCO
PT_LABELS = {
    "person":        "pessoa",
    "bicycle":       "bicicleta",
    "car":           "carro",
    "motorcycle":    "moto",
    "airplane":      "aviao",
    "bus":           "onibus",
    "train":         "trem",
    "truck":         "caminhao",
    "boat":          "barco",
    "traffic light": "semaforo",
    "fire hydrant":  "hidrometro",
    "stop sign":     "placa pare",
    "bench":         "banco",
    "bird":          "passaro",
    "cat":           "gato",
    "dog":           "cachorro",
    "horse":         "cavalo",
    "sheep":         "ovelha",
    "cow":           "vaca",
    "elephant":      "elefante",
    "bear":          "urso",
    "zebra":         "zebra",
    "giraffe":       "girafa",
    "backpack":      "mochila",
    "umbrella":      "guarda-chuva",
    "handbag":       "bolsa",
    "tie":           "gravata",
    "suitcase":      "mala",
    "bottle":        "garrafa",
    "wine glass":    "taca",
    "cup":           "xicara",
    "fork":          "garfo",
    "knife":         "faca",
    "spoon":         "colher",
    "bowl":          "tigela",
    "banana":        "banana",
    "apple":         "maca",
    "sandwich":      "sanduiche",
    "orange":        "laranja",
    "pizza":         "pizza",
    "donut":         "rosquinha",
    "cake":          "bolo",
    "chair":         "cadeira",
    "couch":         "sofa",
    "bed":           "cama",
    "dining table":  "mesa",
    "toilet":        "vaso sanitario",
    "tv":            "televisao",
    "laptop":        "notebook",
    "mouse":         "mouse",
    "keyboard":      "teclado",
    "cell phone":    "celular",
    "microwave":     "micro-ondas",
    "oven":          "forno",
    "refrigerator":  "geladeira",
    "book":          "livro",
    "clock":         "relogio",
    "scissors":      "tesoura",
    "toothbrush":    "escova de dente",
}

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")


class NoxCamera:
    """
    Modulo de visao computacional da NOX AI.
    Abre a camera, roda YOLOv8 frame a frame e exibe deteccoes.
    """

    def __init__(self, log_fn=None, confidence=0.45, camera_index=0):
        """
        log_fn      : funcao callback para enviar logs para a interface (opcional)
        confidence  : limiar minimo de confianca para exibir deteccao (0-1)
        camera_index: indice da camera (0 = default)
        """
        self.log_fn       = log_fn or print
        self.confidence   = confidence
        self.camera_index = camera_index

        self._running     = False
        self._thread      = None
        self._model       = None
        self._last_report = {}   # evita spam de log repetindo o mesmo objeto
        self._report_q    = queue.Queue()

    # ── API publica ───────────────────────────────────────────────────────

    def start(self):
        """Inicia a camera em thread separada."""
        if self._running:
            return
        if not CV2_OK:
            self._log("› [VISION] opencv nao instalado — pip install opencv-python")
            return
        if not YOLO_OK:
            self._log("› [VISION] ultralytics nao instalado — pip install ultralytics")
            return

        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Para a camera."""
        self._running = False

    def is_running(self):
        return self._running

    # ── Internos ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        try:
            self.log_fn(msg)
        except Exception:
            print(msg)

    def _load_model(self):
        """Carrega YOLOv8n (baixa automaticamente se necessario ~6MB)."""
        self._log("› [VISION] carregando modelo YOLOv8...")
        try:
            self._model = YOLO(MODEL_PATH)
            self._log("› [VISION] modelo pronto")
        except Exception as e:
            self._log(f"› [VISION] erro ao carregar modelo: {e}")
            self._running = False

    def _get_color(self, label: str):
        return CATEGORY_COLORS.get(label.lower(), CATEGORY_COLORS["default"])

    def _translate(self, label: str) -> str:
        return PT_LABELS.get(label.lower(), label)

    def _draw_detection(self, frame, box, label: str, conf: float):
        """Desenha caixa e label estilo NOX sobre o frame."""
        x1, y1, x2, y2 = map(int, box)
        color    = self._get_color(label)
        pt_label = self._translate(label)
        text     = f"{pt_label} {conf:.0%}"

        # caixa principal
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # cantos estilo NOX (brackets)
        sz = 12
        cv2.line(frame, (x1, y1), (x1 + sz, y1), color, 3)
        cv2.line(frame, (x1, y1), (x1, y1 + sz), color, 3)
        cv2.line(frame, (x2, y1), (x2 - sz, y1), color, 3)
        cv2.line(frame, (x2, y1), (x2, y1 + sz), color, 3)
        cv2.line(frame, (x1, y2), (x1 + sz, y2), color, 3)
        cv2.line(frame, (x1, y2), (x1, y2 - sz), color, 3)
        cv2.line(frame, (x2, y2), (x2 - sz, y2), color, 3)
        cv2.line(frame, (x2, y2), (x2, y2 - sz), color, 3)

        # fundo do label
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)

        # texto do label
        cv2.putText(
            frame, text, (x1 + 3, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (10, 10, 10), 1, cv2.LINE_AA
        )

    def _draw_overlay(self, frame, detections: list):
        """Desenha overlay NOX no topo do frame."""
        h, w = frame.shape[:2]

        # barra escura no topo
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 36), (5, 6, 10), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # titulo
        cv2.putText(
            frame, "NOX AI  //  VISION MODULE", (12, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 210, 122), 1, cv2.LINE_AA
        )

        # contagem de deteccoes
        n_pessoas  = sum(1 for d in detections if d["label"] == "person")
        n_objetos  = len(detections) - n_pessoas
        info = f"pessoas: {n_pessoas}  |  objetos: {n_objetos}  |  total: {len(detections)}"
        cv2.putText(
            frame, info, (w - 400, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1, cv2.LINE_AA
        )

        # linha dourada abaixo do header
        cv2.line(frame, (0, 36), (w, 36), (255, 210, 122), 1)

    def _report_detections(self, detections: list):
        """Envia log apenas quando aparece algo novo (evita spam)."""
        current = {}
        for d in detections:
            lbl = d["label"]
            current[lbl] = current.get(lbl, 0) + 1

        if current != self._last_report:
            if current:
                parts = []
                for lbl, cnt in current.items():
                    pt = self._translate(lbl)
                    parts.append(f"{cnt}x {pt}" if cnt > 1 else pt)
                self._log("› [VISION] detectado: " + ", ".join(parts))
            self._last_report = current

    def _run(self):
        """Loop principal da camera."""
        # carrega modelo
        self._load_model()
        if not self._running or self._model is None:
            return

        # abre camera
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self._log(f"› [VISION] camera {self.camera_index} nao encontrada")
            self._running = False
            return

        # configuracoes de captura
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 30)

        self._log("› [VISION] camera ativa — pressione Q para fechar")

        frame_count  = 0
        last_results = []

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame_count += 1

            # roda YOLO a cada 3 frames (equilibrio velocidade/precisao)
            if frame_count % 3 == 0:
                try:
                    results = self._model(
                        frame,
                        conf=self.confidence,
                        verbose=False,
                        stream=False,
                    )
                    last_results = []
                    for r in results:
                        for box in r.boxes:
                            label = self._model.names[int(box.cls[0])]
                            conf  = float(box.conf[0])
                            last_results.append({
                                "label": label,
                                "conf":  conf,
                                "box":   box.xyxy[0].tolist(),
                            })
                    self._report_detections(last_results)
                except Exception as e:
                    self._log(f"› [VISION] erro na deteccao: {e}")

            # desenha deteccoes do ultimo resultado
            for det in last_results:
                self._draw_detection(frame, det["box"], det["label"], det["conf"])

            # overlay NOX
            self._draw_overlay(frame, last_results)

            cv2.imshow("NOX AI — VISION", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:  # Q ou ESC
                break

        cap.release()
        cv2.destroyAllWindows()
        self._running = False
        self._last_report = {}
        self._log("› [VISION] camera encerrada")


# ══════════════════════════════════════════════════════════════════════════
#  Uso standalone (teste direto: python camera.py)
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not CV2_OK:
        print("Instale opencv: pip install opencv-python")
        sys.exit(1)
    if not YOLO_OK:
        print("Instale ultralytics: pip install ultralytics")
        sys.exit(1)

    print("NOX VISION — iniciando...")
    cam = NoxCamera(log_fn=print, confidence=0.45)
    cam.start()

    try:
        while cam.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        cam.stop()
        print("Encerrado.")
