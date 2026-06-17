import asyncio
import shlex

from .models import ServiceResponse

RESTART_LOG = "/tmp/jarvis-dev-restart.log"
RESTART_DELAY_SECONDS = 2


async def run_service_command(*command: str) -> ServiceResponse:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    output = stdout.decode("utf-8", errors="replace").strip()
    error_output = stderr.decode("utf-8", errors="replace").strip()
    return ServiceResponse(
        ok=process.returncode == 0,
        output=output,
        stderr=error_output,
        command=shlex.join(command),
        returncode=process.returncode,
    )


async def systemctl(*args: str) -> ServiceResponse:
    return await run_service_command("systemctl", *args, "jarvis-dev")


async def sudo_systemctl(*args: str) -> ServiceResponse:
    return await run_service_command("sudo", "systemctl", *args, "jarvis-dev")


async def schedule_restart() -> ServiceResponse:
    script = (
        "nohup bash -c '"
        f"echo \"$(date -Is) restart requested; delay={RESTART_DELAY_SECONDS}s\"; "
        f"sleep {RESTART_DELAY_SECONDS}; "
        "sudo systemctl restart jarvis-dev; "
        "rc=$?; "
        "echo \"$(date -Is) restart returncode=${rc}\"; "
        "exit ${rc}"
        f"' >> {shlex.quote(RESTART_LOG)} 2>&1 < /dev/null &"
    )
    response = await run_service_command("bash", "-lc", script)
    if response.ok and not response.output:
        response.output = (
            f"restart scheduled in {RESTART_DELAY_SECONDS} seconds; "
            f"log: {RESTART_LOG}"
        )
    return response
