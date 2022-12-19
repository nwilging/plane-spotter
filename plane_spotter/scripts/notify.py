from dataclasses import dataclass
from typing import Any

import hydra
from hydra.core.config_store import ConfigStore
from omegaconf import MISSING, OmegaConf
from structlog import get_logger

from plane_spotter.adsb import ADSB, ADSBExchange
from plane_spotter.geolocator import Geolocator
from plane_spotter.notification import NotificationBackend, TwitterClient
from plane_spotter.package import airport_code_path


@dataclass
class ADSBConfig:
    api_hostname: str


@dataclass
class ADSBExchangeConfig(ADSBConfig):
    api_key: str
    driver: str = "adsbexchange"


@dataclass
class NotifyConfig:
    pass


@dataclass
class Twitter(NotifyConfig):
    key_id: str
    key_secret: str
    driver: str = "twitter"


@dataclass
class Config:
    adsb_backend: ADSBConfig
    notification_backend: NotifyConfig


@dataclass
class Airplane:
    registration: str | None
    icao_hex_id: str | None


cs = ConfigStore.instance()
cs.store(name="main", node=Config)
cs.store(group="adsb_backend", name="adsbexchange", node=ADSBExchangeConfig)
cs.store(group="notification_backend", name="twitter", node=Twitter)
cs.store(name="airplane", node=Airplane)

logger = get_logger(__name__)


@hydra.main(version_base=None, config_path=".", config_name="notify")
def notify(cfg: Config) -> None:
    log = logger.bind(
        adsb_backend=cfg.adsb_backend["driver"],
        notification_backend=cfg.notification_backend["driver"],
    )
    log.info("starting")

    adsb_backend: ADSB
    notification_backend: NotificationBackend
    geolocator = Geolocator(airport_code_file=airport_code_path())

    log.info("instantiating ADS-B backend")
    if cfg.adsb_backend["driver"] == "adsbexchange":
        adsb_backend = ADSBExchange(
            key=cfg.adsb_backend["api_key"], hostname=cfg.adsb_backend["api_hostname"]
        )
    else:
        raise ValueError(f"backend not known: {cfg.adsb_backend['driver']}")

    log.info("instantiating notification backend")
    if cfg.notification_backend["driver"] == "twitter":
        notification_backend = TwitterClient()

    response = adsb_backend.aircraft_last_position_by_hex_id(
        hex_id=cfg.airplane["icao_hex_id"]
    ).json()
    lat = response["lat"]
    lon = response["lon"]
    log.info(f"Plane last known location", lat=lat, lon=lon)

    nearest_airport = geolocator.lookup_airport(
        coordinates=(lat, lon), max_distance=1.0
    )
    if nearest_airport is None:
        log.info("not near any known airport")
        return

    log.info(nearest_airport)


if __name__ == "__main__":
    notify()
