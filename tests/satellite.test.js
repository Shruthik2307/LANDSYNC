import { describe, expect, it, vi, beforeEach } from 'vitest'
import { SatelliteTokenManager, tileToBBox } from '../server/satellite-utils.mjs'

describe('Satellite Utilities', () => {
  describe('tileToBBox', () => {
    it('correctly converts XYZ to bounding box', () => {
      // Zoom 0, Tile 0,0 should be the whole world (within Web Mercator limits)
      const bbox0 = tileToBBox(0, 0, 0)
      expect(bbox0.west).toBe(-180)
      expect(bbox0.east).toBe(180)
      expect(bbox0.north).toBeCloseTo(85.0511, 4)
      expect(bbox0.south).toBeCloseTo(-85.0511, 4)

      // Test a specific tile
      const bbox1 = tileToBBox(10, 512, 340)
      expect(bbox1.west).toBeCloseTo(-180 + (512 / 1024) * 360)
      expect(bbox1.east).toBeCloseTo(-180 + (513 / 1024) * 360)
    })
  })

  describe('SatelliteTokenManager', () => {
    let manager
    const mockClientId = 'test-client-id'
    const mockClientSecret = 'test-client-secret'

    beforeEach(() => {
      process.env.SENTINELHUB_CLIENT_ID = mockClientId
      process.env.SENTINELHUB_CLIENT_SECRET = mockClientSecret
      manager = new SatelliteTokenManager()
      vi.stubGlobal('fetch', vi.fn())
    })

    it('fetches a token and caches it', async () => {
      const mockToken = 'access-token-123'
      fetch.mockResolvedValue({
        ok: true,
        json: async () => ({ access_token: mockToken, expires_in: 3600 }),
      })

      const token1 = await manager.getToken()
      expect(token1).toBe(mockToken)
      expect(fetch).toHaveBeenCalledTimes(1)

      const token2 = await manager.getToken()
      expect(token2).toBe(mockToken)
      expect(fetch).toHaveBeenCalledTimes(1) // cached
    })

    it('refreshes token before expiration', async () => {
      const mockToken1 = 'token-1'
      const mockToken2 = 'token-2'

      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: mockToken1, expires_in: 10 }), // 10s expiry
      })
      fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: mockToken2, expires_in: 3600 }),
      })

      await manager.getToken()

      // Fast forward time (simulated by manually adjusting expiryTimestamp)
      manager.expiryTimestamp = Date.now() + 30000 // 30s from now (within 60s buffer)

      const token = await manager.getToken()
      expect(token).toBe(mockToken2)
      expect(fetch).toHaveBeenCalledTimes(2)
    })

    it('throws error when credentials are missing', async () => {
      delete process.env.SENTINELHUB_CLIENT_ID
      const failManager = new SatelliteTokenManager()
      await expect(failManager.getToken()).rejects.toThrow('Missing SENTINELHUB_CLIENT_ID')
    })

    it('handles auth failure', async () => {
      fetch.mockResolvedValue({
        ok: false,
        status: 401,
        text: async () => 'Unauthorized',
      })

      await expect(manager.getToken()).rejects.toThrow('Auth failed: 401 Unauthorized')
    })
  })
})
