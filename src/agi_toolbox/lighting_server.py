"""Independent local lighting capability. Run with grace-lighting."""
import argparse
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .lighting_catalog import read_catalog, resolve_effect, save_preset
from .lighting_device import LightingDevice


def create_app(device=None):
    rgb = device if device is not None else LightingDevice()

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(rgb.start)
        try:
            yield
        finally:
            await asyncio.to_thread(rgb.close)

    app = FastAPI(title='Grace lighting capability', lifespan=lifespan, docs_url=None, redoc_url=None)

    async def payload(request):
        try:
            value = await request.json()
            if not isinstance(value, dict):
                raise ValueError('Expected an object')
            return value
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error)) from None

    @app.put('/api/lighting')
    async def apply(request: Request):
        value = await payload(request)
        try:
            effect = await asyncio.to_thread(resolve_effect, value)
            if effect is None:
                result = await asyncio.to_thread(rgb.clear_effect)
                return {**result, 'selected': 'default', 'reason': value.get('reason', '')}
            return await asyncio.to_thread(rgb.set_effect, effect)
        except (ValueError, TypeError, OSError) as error:
            raise HTTPException(422, str(error)) from None
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from None

    @app.put('/api/lighting/speech')
    async def speech(request: Request):
        value = await payload(request)
        try:
            return await asyncio.to_thread(rgb.speech_event, **value)
        except (ValueError, TypeError, OSError) as error:
            raise HTTPException(422, str(error)) from None
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from None

    @app.get('/api/lighting')
    async def status():
        return await asyncio.to_thread(rgb.status)

    @app.delete('/api/lighting')
    async def stop():
        return await asyncio.to_thread(rgb.clear_effect)

    @app.get('/api/lighting/catalog')
    async def catalog():
        try:
            return await asyncio.to_thread(read_catalog)
        except (ValueError, TypeError, OSError) as error:
            raise HTTPException(422, str(error)) from None

    @app.put('/api/lighting/catalog')
    async def save(request: Request):
        value = await payload(request)
        try:
            return await asyncio.to_thread(save_preset, **value)
        except (ValueError, TypeError, OSError) as error:
            raise HTTPException(422, str(error)) from None

    return app


def main():
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8854)
    args = parser.parse_args()
    uvicorn.run(create_app(), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
