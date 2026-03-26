# Corrector de Valencià — Frontend web (Fase 1)

Aplicació web per a la correcció de textos en valencià estàndard universitari, dissenyada per al SLPL de la Universitat de València.

## Arquitectura

```
Tècnic → Cloudflare Pages (frontend) → Cloudflare Function (proxy) → API d’Anthropic (Claude)
```

- **Frontend**: Pàgina HTML estàtica (`index.html`) amb interfície per a enganxar text
- **Backend**: Cloudflare Function (`functions/api/corregir.js`) que fa de proxy segur cap a l’API d’Anthropic
- **IA**: Claude (Sonnet) amb system prompt normatiu que analitza per 4 capes (SINT, MORF, LÈX, ORTO)

## Desplegament a Cloudflare Pages

### 1. Requisits previs

- Compte de Cloudflare (gratuït): https://dash.cloudflare.com/sign-up
- Clau d’API d’Anthropic activa
- (Opcional) Repositori GitHub amb aquest projecte

### 2. Opció A: Desplegament des de GitHub (recomanat)

1. Puja aquest directori a un repositori de GitHub.
2. A Cloudflare Dashboard → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**.
3. Selecciona el repositori i configura:
   - **Build command**: (deixar buit, no cal compilar)
   - **Build output directory**: `/` (arrel del projecte)
4. A **Settings** → **Environment variables**, afegeix:
   - `ANTHROPIC_API_KEY` = la teua clau d’API d’Anthropic
   - (**Important**: marca-la com a "Encrypted")
5. Fes clic a **Save and Deploy**.

### 3. Opció B: Desplegament directe amb Wrangler

```bash
npm install -g wrangler
wrangler login
wrangler pages deploy . --project-name=corrector-valencia
wrangler pages secret put ANTHROPIC_API_KEY --project-name=corrector-valencia
```

### 4. Verificació

Un cop desplegat, ves a l’URL proporcionada per Cloudflare, enganxa un text de prova i polsa "Corregeix".

## Estructura del projecte

```
correccio-valenciana-web/
├── index.html                  # Frontend (HTML + CSS + JS)
├── functions/
│   └── api/
│       └── corregir.js         # Cloudflare Function (proxy API)
├── system-prompt.md            # System prompt de referència (no es desplega)
└── README.md                   # Aquesta documentació
```

## Configuració

### Model de Claude

Per defecte, s’utilitza `claude-sonnet-4-20250514`. Per canviar-lo, edita la línia `model` a `functions/api/corregir.js`.

### Límit de text

El límit actual és de 100.000 caràcters (aprox. 15.000 paraules). Ajustable a `functions/api/corregir.js`.

## Cost estimat

- **Cloudflare Pages**: Gratuït (100.000 invocacions de Functions/dia)
- **API d’Anthropic**: ~0,003–0,01 € per correcció (depenent de la llargada del text)
- Per a 5 tècnics amb ~20 correccions/dia cadascun: ~1–3 €/dia estimat

## Fases futures

- **Fase 2**: Suport per a fitxers .docx i .pptx (extracció de text al navegador amb mammoth.js)
- **Fase 3**: Generació de .docx corregit amb destacats grocs (requereix backend Python)

## Autor

Servei de Llengües i Política Lingüística (SLPL), Universitat de València

