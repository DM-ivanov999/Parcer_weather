// Vercel Serverless Function
// Файл: api/uv.js
// Деплой: vercel deploy

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY;

export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ ok: false, error: 'Method not allowed' });
  }

  const { city, fields } = req.body;

  if (!city) {
    return res.status(400).json({ ok: false, error: 'City is required' });
  }

  try {
    const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_uv_for_banner`, {
      method: 'POST',
      headers: {
        'apikey': SUPABASE_ANON_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        p_city: city,
        p_fields: fields || null
      })
    });

    const data = await response.json();
    return res.status(200).json(data);

  } catch (err) {
    return res.status(500).json({ ok: false, error: err.message });
  }
}
