"""Component that will help set the Dlib face detect processing."""
import logging
import io

from homeassistant.core import split_entity_id
# pylint: disable=unused-import
from homeassistant.components.image_processing import PLATFORM_SCHEMA  # noqa
from homeassistant.components.image_processing import (
    ImageProcessingFaceEntity, CONF_SOURCE, CONF_ENTITY_ID, CONF_NAME)

_LOGGER = logging.getLogger(__name__)

ATTR_LOCATION = 'location'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dlib Face detection platform."""
    entities = []
    for camera in config[CONF_SOURCE]:
        entities.append(DlibFaceDetectEntity(
            camera[CONF_ENTITY_ID], camera.get(CONF_NAME)
        ))

    add_entities(entities)


class DlibFaceDetectEntity(ImageProcessingFaceEntity):
    """Dlib Face API entity for identify."""

    def __init__(self, camera_entity, name=None):
        """Initialize Dlib face entity."""
        super().__init__()

        self._camera = camera_entity

        if name:
            self._name = name
        else:
            self._name = "Dlib Face {0}".format(
                split_entity_id(camera_entity)[1])

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def process_image(self, image):
        """Process image."""
        import face_recognition  # pylint: disable=import-error

        fak_file = io.BytesIO(image)
        fak_file.name = 'snapshot.jpg'
        fak_file.seek(0)

        image = face_recognition.load_image_file(fak_file)
        face_locations = face_recognition.face_locations(image)

        face_locations = [{ATTR_LOCATION: location}
                          for location in face_locations]

        self.process_faces(face_locations, len(face_locations))
