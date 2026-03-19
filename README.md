# TANEU — Motor de Traducció Automàtica Neuronal castellà→valencià

**Servei de Llengües i Política Lingüística (SLPL)**
Universitat de València — Secció d'Assessorament Lingüístic

**Interfície pública:** [https://sancoipv.github.io/tan-slpl-uv/](https://sancoipv.github.io/tan-slpl-uv/)

---

## Descripció

TANEU és un sistema de traducció automàtica neuronal (TAN) especialitzat en la parella de llengües **castellà → valencià** en l'àmbit universitari. El model s'ha entrenat a partir del motor TAN aina-translator-es-ca desenvolupat pel Language Technologies Lab del BSC-CNS dins el Projecte Aina, per a produir traduccions en **valencià normatiu universitari**, d'acord amb els *Criteris per als usos lingüístics de les universitats valencianes*.

---

## Estructura del projecte

```
taneu/
├── models/           # Models TAN entrenats i adaptats
├── corpus/
│   ├── raw/          # Corpus originals descarregats (sense modificar)
│   ├── clean/        # Corpus filtrats i netejats per a l'entrenament
│   └── postedicions/ # Traduccions revisades pels tècnics del SLPL
├── scripts/          # Scripts Python per a entrenament, avaluació i traducció
├── webapp/           # Interfície web (FastAPI + Streamlit)
├── logs/             # Registre d'activitat i errors
├── outputs/          # Documents traduïts generats pel sistema
├── .venv/            # Entorn virtual Python (no versionat)
├── config.yaml       # Configuració principal del sistema
├── requirements.txt  # Dependències Python
└── README.md         # Aquest fitxer
```

---

## Requisits del sistema

- Python 3.10 o superior
- pip actualitzat
- GPU recomanada per a l'entrenament (CUDA compatible)

---

## Instal·lació

```bash
# 1. Clonar o descomprimir el projecte
cd /SLPL/taneu/

# 2. Crear l'entorn virtual
python3 -m venv .venv

# 3. Activar l'entorn virtual
source .venv/bin/activate

# 4. Instal·lar les dependències
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Criteris lingüístics aplicats

El sistema genera text en **valencià normatiu universitari** seguint els criteris aprovats per les universitats valencianes:

| Característica | Forma correcta | Forma evitada |
|---|---|---|
| Demostratius formals | aquest/aquesta/aquell | este/eixe |
| Verbs incoatius | serveix, pateix, ofereix | servix, patix, oferix |
| Possessius | meua/teua/seua | meva/teva/seva |
| Accentuació | anglès/francès | anglés/francés |
| Lèxic culte | avui, menut, aprendre | hui, xicotet, dependre |
| Plurals | discos/textos | discs/texts |
| Participis | complit/oferit/establit | complert/ofert/establert |

---

## Ús bàsic

```bash
# Activar l'entorn virtual
source .venv/bin/activate

# Traduir un fitxer de text
python scripts/traduir.py --input fitxer.txt --output traduccio.txt

# Iniciar la interfície web
streamlit run webapp/app.py
```

---

## Avaluació

El sistema utilitza les mètriques estàndard de traducció automàtica:
- **BLEU** (sacrebleu)
- **COMET** (unbabel-comet)

---

## Contacte

**Servei de Llengües i Política Lingüística**
Universitat de València
[slpl@uv.es](mailto:slpl@uv.es)
