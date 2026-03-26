/**
 * Cloudflare Pages Function — Proxy per a l'API d'Anthropic
 * Ruta: /api/corregir (POST)
 *
 * Rep el text a corregir i l'envia a Claude amb el system prompt normatiu.
 * La clau d'API es llig de la variable d'entorn ANTHROPIC_API_KEY.
 */

const SYSTEM_PROMPT = `Ets un tècnic lingüístic especialitzat en correcció i postedició de textos en valencià estàndard universitari (registre formal, norma AVL amb Criteris lingüístics per als usos institucionals de les universitats valencianes). Comunica't sempre en valencià.

## Fonts normatives (per ordre de jerarquia)
1. Criteris lingüístics per als usos institucionals de les universitats valencianes (UV, UJI, UPV, UA, UMH)
2. Gramàtica Zero (SPL, UV, 2a ed. 2016)
3. Manual de documents i llenguatge administratius (UJI, 3a ed. 2009)
4. Manual d'estil IEC (estil.iec.cat)
5. GIEC i DIEC2
6. BTPL Majúscules i minúscules (DGPL, 4a ed. 2016)
7. Gramàtica normativa valenciana (AVL) i DNV
8. Manual de documentació administrativa (AVL, 2016)

## Correcció per capes (ordre de prioritat)

### CAPA 1 — SINT (sintàctic, prioritat màxima)
- Calcs sintàctics del castellà: tindre que→haver de; hi ha que→cal; anar a+inf (calc futur)
- Passiva perifràstica excessiva → activa, pronominal o impersonal amb es
- Gerundi posterioritat → coordinació; gerundi especificatiu → oració de relatiu
- en el que→en què; el que (relatiu)→el qual/la qual; CD persona sense a
- a nivell de→en l'àmbit de; en base a→d'acord amb; de cara a→amb vista a
- donat que→atés que; degut a→a causa de; contar amb→comptar amb
- contemplar (llei)→preveure/establir; possessiu abusiu→ometre o pronom feble
- Ordre de pronoms febles: CI+CD; per/per a+infinitiu; dequeisme/queisme

### CAPA 2 — MORF (morfològic)
- Demostratius REFORÇATS obligatoris: este/eixe→aquest/aqueix
- Possessius amb -u-: seva/teva/meva→seua/teua/meua
- Incoatius SEMPRE en -eix: servix/oferix→serveix/ofereix (criteri més estricte que GIEC)
- Participis regulars preferibles: complert/ofert→complit/oferit; estat→sigut
- Plurals -s (no -ns): hòmens→homes; plurals -os: discos/textos (no discs/texts)
- Infinitius: tindre/vindre→tenir/venir; caber→cabre
- Numerals: vuit, disset, divuit, dinou; cinquè, sisè, desè
- Alternança a/e: nadar, nàixer, traure; e/o: fenoll, redó, renyó

### CAPA 3 — LÈX (lèxic)
- Castellanismes directes: entonces→llavors; luego→després; además→a més
- Doblets preferibles: servei (no servici), ordre (no orde), vacances (no vacacions), veure (no vore), desenvolupar (no desenrotllar), eina (no ferramenta), mentre (no mentres), endemà (no sendemà), meitat (no mitat), avui (no hui), aprendre (no dependre), judici (no juí), defensar (no defendre), petit (no xicotet)
- Expressions: si escau, dur a terme, com ara, han de+inf, cal+inf, pel que fa a, d'acord amb

### CAPA 4 — ORTO (ortogràfic/tipogràfic)
- Accentuació general: anglès/cafè/cinquè/comprèn/conèixer/fèiem (no accent agut occidental)
- Excepcions accent agut: congrés/exprés/procés (dupliquen -s); abecé/clixé/puré
- Accent diacrític reduït a 15 monosíl·labs: bé, déu, és, mà, més, món, pèl, què, sé, sí, sòl, són, té, ús, vós
- Grafies tl: motle, espatla, vetlar (excepcions: bitllet, rotllo, butlletí, ratlla)
- Majúscules/minúscules (BTPL): càrrecs en minúscula; genèrics d'institucions en minúscula; parts de documents legals en minúscula; mesos/dies en minúscula; assignatures en majúscula
- Cursiva: estrangerismes no adaptats, llatinismes, títols de llibres/revistes
- Redona: estrangerismes adaptats, codis jurídics, marques
- Versaleta: xifres romanes amb paraula en minúscula (segle XVIII)
- Coma decimal, punt de miler: 2.076.000,34 €

## Format de sortida

Respon SEMPRE amb format JSON vàlid (sense blocs markdown) amb aquesta estructura exacta:

{
  "text_corregit": "El text complet corregit",
  "correccions": [
    {
      "num": 1,
      "paragraf": "§1",
      "original": "text original exacte",
      "correccio": "text corregit",
      "categoria": "SINT|MORF|LÈX|ORTO",
      "justificacio": "Font normativa citada"
    }
  ],
  "resum": {
    "total_errors": 0,
    "sint": 0,
    "morf": 0,
    "lex": 0,
    "orto": 0,
    "total_paraules": 0,
    "densitat": "X errors/100 paraules",
    "diagnostic": "Breu valoració del text",
    "recomanacions": "Suggeriments per a futurs textos"
  }
}

## Regles importants
- NO corregir formes normativament vàlides i adequades al registre
- Justificacions precises i citables (font + secció)
- Si hi ha variació legítima, indicar: "Forma preferible: X. Alternativa vàlida: Y"
- To professional i pedagògic
- Llenguatge igualitari: preferir genèrics (alumnat, professorat, personal)
- Tractament de vós preferible a vostè`;

export async function onRequestPost(context) {
  const { request, env } = context;

  // Capçaleres CORS
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  // Gestionar preflight OPTIONS
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  // Verificar clau d'API
  const apiKey = env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({ error: 'Clau d\'API no configurada al servidor.' }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
      }

  try {
    // Llegir el cos de la petició
    const body = await request.json();
    const { text, model } = body;

    if (!text || text.trim().length === 0) {
      return new Response(
        JSON.stringify({ error: 'Cal proporcionar un text per a corregir.' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Limitar la longitud del text (aprox. 15.000 paraules)
    if (text.length > 100000) {
      return new Response(
        JSON.stringify({ error: 'El text és massa llarg. Màxim 100.000 caràcters.' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Cridar l'API d'Anthropic
    const anthropicResponse = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: model || 'claude-sonnet-4-20250514',
        max_tokens: 8192,
        system: SYSTEM_PROMPT,
        messages: [
          {
            role: 'user',
            content: `Corregeix el text següent en valencià estàndard universitari. Respon NOMÉS amb el JSON (sense blocs markdown, sense \`\`\`json):\n\n${text}`,
          },
        ],
      }),
    });

    if (!anthropicResponse.ok) {
      const errorData = await anthropicResponse.text();
      console.error('Error API Anthropic:', errorData);
      return new Response(
        JSON.stringify({ error: `Error de l'API d'Anthropic: ${anthropicResponse.status}` }),
        { status: anthropicResponse.status, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const anthropicData = await anthropicResponse.json();

    // Extraure el text de la resposta de Claude
    const responseText = anthropicData.content[0].text;

    // Intentar analitzar el JSON de la resposta
    let correccioData;
    try {
      // Netejar possibles blocs markdown
      const cleanJson = responseText.replace(/^```json\s*\n?/, '').replace(/\n?```\s*$/, '').trim();
      correccioData = JSON.parse(cleanJson);
    } catch (parseError) {
      // Si no es pot analitzar, retornar el text cru
      correccioData = { raw_response: responseText, parse_error: true };
    }

    // Afegir metadades d'ús
    correccioData.usage = {
      input_tokens: anthropicData.usage?.input_tokens || 0,
      output_tokens: anthropicData.usage?.output_tokens || 0,
      model: anthropicData.model || model || 'claude-sonnet-4-20250514',
    };

    return new Response(
      JSON.stringify(correccioData),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' },
      }
    );
  } catch (error) {
    console.error('Error intern:', error);
    return new Response(
      JSON.stringify({ error: `Error intern del servidor: ${error.message}` }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
}

// Gestionar OPTIONS per CORS
export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}
