"""Support for functionality to download files."""
import logging
import os
import re
import threading

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util import sanitize_filename

_LOGGER = logging.getLogger(__name__)

ATTR_FILENAME = 'filename'
ATTR_SUBDIR = 'subdir'
ATTR_URL = 'url'
ATTR_OVERWRITE = 'overwrite'

CONF_DOWNLOAD_DIR = 'download_dir'

DOMAIN = 'downloader'
DOWNLOAD_FAILED_EVENT = 'download_failed'
DOWNLOAD_COMPLETED_EVENT = 'download_completed'

SERVICE_DOWNLOAD_FILE = 'download_file'

SERVICE_DOWNLOAD_FILE_SCHEMA = vol.Schema({
    vol.Required(ATTR_URL): cv.url,
    vol.Optional(ATTR_SUBDIR): cv.string,
    vol.Optional(ATTR_FILENAME): cv.string,
    vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOWNLOAD_DIR): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Listen for download events to download files."""
    download_path = config[DOMAIN][CONF_DOWNLOAD_DIR]

    # If path is relative, we assume relative to HASS config dir
    if not os.path.isabs(download_path):
        download_path = hass.config.path(download_path)

    if not os.path.isdir(download_path):
        _LOGGER.error(
            "Download path %s does not exist. File Downloader not active",
            download_path)

        return False

    def download_file(service):
        """Start thread to download file specified in the URL."""
        def do_download():
            """Download the file."""
            try:
                url = service.data[ATTR_URL]

                subdir = service.data.get(ATTR_SUBDIR)

                filename = service.data.get(ATTR_FILENAME)

                overwrite = service.data.get(ATTR_OVERWRITE)

                if subdir:
                    subdir = sanitize_filename(subdir)

                final_path = None

                req = requests.get(url, stream=True, timeout=10)

                if req.status_code != 200:
                    _LOGGER.warning(
                        "downloading '%s' failed, status_code=%d",
                        url,
                        req.status_code)
                    hass.bus.fire(
                        "{}_{}".format(DOMAIN, DOWNLOAD_FAILED_EVENT), {
                            'url': url,
                            'filename': filename
                            })

                else:
                    if filename is None and \
                       'content-disposition' in req.headers:
                        match = re.findall(r"filename=(\S+)",
                                           req.headers['content-disposition'])

                        if match:
                            filename = match[0].strip("'\" ")

                    if not filename:
                        filename = os.path.basename(url).strip()

                    if not filename:
                        filename = 'ha_download'

                    # Remove stuff to ruin paths
                    filename = sanitize_filename(filename)

                    # Do we want to download to subdir, create if needed
                    if subdir:
                        subdir_path = os.path.join(download_path, subdir)

                        # Ensure subdir exist
                        if not os.path.isdir(subdir_path):
                            os.makedirs(subdir_path)

                        final_path = os.path.join(subdir_path, filename)

                    else:
                        final_path = os.path.join(download_path, filename)

                    path, ext = os.path.splitext(final_path)

                    # If file exist append a number.
                    # We test filename, filename_2..
                    if not overwrite:
                        tries = 1
                        final_path = path + ext
                        while os.path.isfile(final_path):
                            tries += 1

                            final_path = "{}_{}.{}".format(path, tries, ext)

                    _LOGGER.debug("%s -> %s", url, final_path)

                    with open(final_path, 'wb') as fil:
                        for chunk in req.iter_content(1024):
                            fil.write(chunk)

                    _LOGGER.debug("Downloading of %s done", url)
                    hass.bus.fire(
                        "{}_{}".format(DOMAIN, DOWNLOAD_COMPLETED_EVENT), {
                            'url': url,
                            'filename': filename
                            })

            except requests.exceptions.ConnectionError:
                _LOGGER.exception("ConnectionError occurred for %s", url)
                hass.bus.fire(
                    "{}_{}".format(DOMAIN, DOWNLOAD_FAILED_EVENT), {
                        'url': url,
                        'filename': filename
                        })

                # Remove file if we started downloading but failed
                if final_path and os.path.isfile(final_path):
                    os.remove(final_path)

        threading.Thread(target=do_download).start()

    hass.services.register(DOMAIN, SERVICE_DOWNLOAD_FILE, download_file,
                           schema=SERVICE_DOWNLOAD_FILE_SCHEMA)

    return True
