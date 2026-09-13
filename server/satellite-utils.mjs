export class SatelliteTokenManager {
  constructor() {
    this.accessToken = null
    this.expiryTimestamp = 0
    this.clientId = process.env.SENTINELHUB_CLIENT_ID
    this.clientSecret = process.env.SENTINELHUB_CLIENT_SECRET
    this.authUrl = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
  }

  async getToken(forceRefresh = false) {
    const now = Date.now()
    if (!forceRefresh && this.accessToken && now < this.expiryTimestamp - 60000) {
      return this.accessToken
    }

    if (!this.clientId || !this.clientSecret) {
      throw new Error('Missing SENTINELHUB_CLIENT_ID or SENTINELHUB_CLIENT_SECRET')
    }

    const params = new URLSearchParams()
    params.append('grant_type', 'client_credentials')
    params.append('client_id', this.clientId)
    params.append('client_secret', this.clientSecret)

    const response = await fetch(this.authUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params,
    })

    if (!response.ok) {
      throw new Error(`Auth failed: ${response.status} ${await response.text()}`)
    }

    const data = await response.json()
    this.accessToken = data.access_token
    this.expiryTimestamp = Date.now() + (data.expires_in * 1000)
    return this.accessToken
  }

  invalidateToken() {
    this.accessToken = null
    this.expiryTimestamp = 0
  }
}

export function tileToBBox(z, x, y) {
  const n = Math.pow(2, z)
  const west = (x / n) * 360 - 180
  const east = ((x + 1) / n) * 360 - 180

  const lonDeg = 180 / Math.PI
  const north = lonDeg * Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n)))
  const south = lonDeg * Math.atan(Math.sinh(Math.PI * (1 - 2 * (y + 1) / n)))

  return { west, south, east, north }
}
