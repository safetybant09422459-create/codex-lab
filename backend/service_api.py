import asyncio

from .models import ServiceResponse


async def systemctl(*args: str) -> ServiceResponse:
    process = await asyncio.create_subprocess_exec(
        "systemctl",
        *args,
        "jarvis-dev",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode("utf-8", errors="replace").strip()
    return ServiceResponse(ok=process.returncode == 0, output=output)
