import subprocess
import logging

logger = logging.getLogger(__name__)

def feed_file_to_vespa(file_path, endpoint_url="http://vespa-feed-container-0.vespa-internal.vespa.svc.cluster.local:8080"):
    """
    Feed a file to Vespa using the vespa-feed-client CLI.
    """
    try:
        command = [
            "vespa-feed-client-cli",
            "--endpoint", endpoint_url,
            file_path
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode == 0:
            logger.info(f"File {file_path} fed successfully to Vespa.")
            return {"success": True, "output": result.stdout}
        else:
            logger.error(f"Error feeding file {file_path} to Vespa: {result.stderr}")
            return {"success": False, "output": result.stderr}

    except Exception as e:
        logger.exception(f"Exception while feeding file {file_path}: {e}")
        return {"success": False, "output": str(e)}
