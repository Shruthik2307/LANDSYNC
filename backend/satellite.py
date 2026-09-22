"""Satellite tile proxy service"""
import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
import hashlib
import logging
from config import SATELLITE_TILE_CACHE_DIR, SATELLITE_TILE_PROVIDERS

logger = logging.getLogger(__name__)

# Tile cache for performance
_tile_cache_memory = {}
MAX_MEMORY_CACHE = 100  # Keep last 100 tiles in memory


async def get_satellite_tile(z: int, x: int, y: int, provider: str = "esri") -> Optional[bytes]:
    """
    Fetch satellite tile from upstream provider with caching

    Args:
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate
        provider: Tile provider name (default: esri)

    Returns:
        Tile image bytes or None if not available
    """
    # Generate cache key
    cache_key = f"{provider}_{z}_{x}_{y}"

    # Check memory cache first
    if cache_key in _tile_cache_memory:
        logger.debug(f"Tile {z}/{x}/{y} served from memory cache")
        return _tile_cache_memory[cache_key]

    # Check disk cache
    cache_file = SATELLITE_TILE_CACHE_DIR / f"{cache_key}.png"
    if cache_file.exists():
        logger.debug(f"Tile {z}/{x}/{y} served from disk cache")
        with open(cache_file, "rb") as f:
            tile_data = f.read()
            # Store in memory cache
            _tile_cache_memory[cache_key] = tile_data
            _cleanup_memory_cache()
            return tile_data

    # Fetch from upstream
    tile_url = SATELLITE_TILE_PROVIDERS.get(provider)
    if not tile_url:
        logger.error(f"Unknown tile provider: {provider}")
        return None

    # Format URL with tile coordinates
    tile_url = tile_url.format(z=z, x=x, y=y)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(tile_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    tile_data = await response.read()

                    # Cache to disk
                    try:
                        with open(cache_file, "wb") as f:
                            f.write(tile_data)
                    except Exception as e:
                        logger.warning(f"Could not cache tile to disk: {e}")

                    # Cache to memory
                    _tile_cache_memory[cache_key] = tile_data
                    _cleanup_memory_cache()

                    logger.info(f"Tile {z}/{x}/{y} fetched from {provider}")
                    return tile_data

                elif response.status == 404:
                    logger.debug(f"Tile {z}/{x}/{y} not found at provider")
                    return None

                else:
                    logger.warning(f"Tile fetch failed with status {response.status}")
                    return None

    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching tile {z}/{x}/{y}")
        return None

    except Exception as e:
        logger.error(f"Error fetching tile {z}/{x}/{y}: {e}")
        return None


def _cleanup_memory_cache():
    """Remove oldest items from memory cache if it exceeds max size"""
    if len(_tile_cache_memory) > MAX_MEMORY_CACHE:
        # Remove oldest entries (FIFO)
        items_to_remove = len(_tile_cache_memory) - MAX_MEMORY_CACHE
        for key in list(_tile_cache_memory.keys())[:items_to_remove]:
            del _tile_cache_memory[key]


def clear_tile_cache():
    """Clear all cached tiles (memory and disk)"""
    global _tile_cache_memory
    _tile_cache_memory = {}

    # Clear disk cache
    for cache_file in SATELLITE_TILE_CACHE_DIR.glob("*.png"):
        try:
            cache_file.unlink()
        except Exception as e:
            logger.warning(f"Could not delete cache file {cache_file}: {e}")

    logger.info("Tile cache cleared")
