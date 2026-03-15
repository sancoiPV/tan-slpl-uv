# -*- coding: utf-8 -*-
"""
actualitza_ngrok.py
-------------------
Llegeix la URL pública HTTPS que ngrok ha assignat en la sessió actual
des de l'API local de ngrok (http://127.0.0.1:4040/api/tunnels),
actualitza frontend/config.js amb la nova URL i fa git commit + push
perquè Netlify redesplegueu automàticament.

Ús (cridat des d'inicia_tan.bat, o manualment):
    python actualitza_ngrok.py

Prerequisits:
    - ngrok ja en marcha (inicia_tan.bat l'arranca primer)
    - git inicialitzat i remot 'origin' configurat (GitHub)
    - requests instal·lat: pip install requests
"""

import re
import sys
import time
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' no instal·lat. Executa: pip install requests")
    sys.exit(1)

# ── Rutes ──────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
CONFIG_JS  = BASE_DIR / "frontend" / "config.js"
NGROK_API  = "http://127.0.0.1:4040/api/tunnels"

# ── Funcions ───────────────────────────────────────────────────────────────────

def get_ngrok_url(intents: int = 15, espera: float = 2.0) -> str | None:
    """
    Interroga l'API local de ngrok fins a obtenir la URL pública HTTPS.
    Reintenta fins a `intents` vegades amb `espera` segons entre reintents.
    """
    for i in range(1, intents + 1):
        try:
            r = requests.get(NGROK_API, timeout=3)
            r.raise_for_status()
            for tunnel in r.json().get("tunnels", []):
                if tunnel.get("proto") == "https":
                    url = tunnel["public_url"].rstrip("/")
                    print(f"   [OK] URL ngrok detectada: {url}")
                    return url
        except Exception:
            pass
        print(f"   Esperant ngrok... ({i}/{intents})")
        time.sleep(espera)
    return None


def update_config_js(ngrok_url: str) -> bool:
    """
    Substitueix al config.js totes les línies de tipus
        url: '...',   // ← CANVIA ...
    que continguen una URL de ngrok per la nova URL.
    Retorna True si el fitxer ha canviat.
    """
    text_original = CONFIG_JS.read_text(encoding="utf-8")

    # Patró: captura qualsevol URL que tingui 'ngrok' al valor
    patro = re.compile(
        r"(url:\s*')[^']*ngrok[^']*('.*)",
        re.IGNORECASE
    )
    text_nou = patro.sub(lambda m: f"{m.group(1)}{ngrok_url}{m.group(2)}",
                         text_original)

    if text_nou == text_original:
        print("   config.js ja tenia la URL correcta, no cal modificar.")
        return False

    CONFIG_JS.write_text(text_nou, encoding="utf-8")
    print(f"   config.js actualitzat amb: {ngrok_url}")
    return True


def git_commit_push(missatge: str = None) -> bool:
    """
    Afegeix frontend/config.js a git, fa commit i push.
    Retorna True si ha anat bé.
    """
    if missatge is None:
        from datetime import datetime
        ara = datetime.now().strftime("%Y-%m-%d %H:%M")
        missatge = f"Auto: actualitza URL ngrok ({ara})"

    cmds = [
        ["git", "-C", str(BASE_DIR), "add", "frontend/config.js"],
        ["git", "-C", str(BASE_DIR), "commit", "-m", missatge],
        ["git", "-C", str(BASE_DIR), "push"],
    ]
    for cmd in cmds:
        resultat = subprocess.run(cmd, capture_output=True, text=True)
        if resultat.returncode != 0:
            # 'nothing to commit' no és un error real
            if "nothing to commit" in resultat.stdout + resultat.stderr:
                print("   git: res a fer (cap canvi).")
                return True
            print(f"   ERROR git: {resultat.stderr.strip()}")
            return False
        if resultat.stdout.strip():
            print(f"   git: {resultat.stdout.strip()}")
    return True


def main():
    print()
    print("=" * 55)
    print("  Actualització automàtica URL ngrok → Netlify")
    print("=" * 55)
    print()

    # 1. Obté la URL de ngrok
    print("[1/3] Llegint URL de ngrok...")
    ngrok_url = get_ngrok_url()
    if not ngrok_url:
        print("\nERROR: No s'ha pogut obtenir la URL de ngrok.")
        print("Comprova que ngrok està en marcha i torna a intentar-ho.")
        sys.exit(1)
    print()

    # 2. Actualitza config.js
    print("[2/3] Actualitzant frontend/config.js...")
    canviat = update_config_js(ngrok_url)
    print()

    # 3. Git commit + push (només si ha canviat el fitxer)
    if canviat:
        print("[3/3] Publicant a Netlify via git push...")
        ok = git_commit_push()
        if ok:
            print()
            print("=" * 55)
            print("  Netlify redesplegarà en ~30-60 segons.")
            print(f"  URL activa: {ngrok_url}")
            print("=" * 55)
        else:
            print()
            print("AVIS: El git push ha fallat.")
            print("Comprova la connexió i el repositori remot.")
            print("La URL de ngrok ÉS correcta al config.js local.")
    else:
        print("[3/3] No cal push (cap canvi).")
        print()
        print("=" * 55)
        print(f"  URL activa: {ngrok_url}")
        print("=" * 55)
    print()


if __name__ == "__main__":
    main()
