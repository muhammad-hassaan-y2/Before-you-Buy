"""Seeded furniture catalog.

Dimensions are the honest published box sizes for each style, so a link the scraper
cannot read still resolves to something a shopper would recognise. Sizes are centimetres
in the order width, depth, height.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from byb_common.contracts import CatalogCandidate, ProductGeometry
from byb_common.parts import build_parts


class Sku(BaseModel):
    sku: str
    name: str
    brand: str
    category: str
    material: str
    price_band: str
    width_cm: float
    depth_cm: float
    height_cm: float
    clearance_cm: float = 10.0
    aliases: tuple[str, ...] = Field(default=())

    @property
    def geometry(self) -> ProductGeometry:
        return ProductGeometry(
            width_cm=self.width_cm, depth_cm=self.depth_cm, height_cm=self.height_cm, clearance_cm=self.clearance_cm
        )

    def tokens(self) -> set[str]:
        """Every word this SKU can be referred to by, aliases included."""
        phrases = {self.brand, self.category, self.material, self.name, *self.aliases}
        words: set[str] = set()
        for phrase in phrases:
            for part in phrase.lower().replace("-", " ").split():
                if len(part) > 1:
                    words.add(part)
        return words

    def as_candidate(self, score: float) -> CatalogCandidate:
        return CatalogCandidate(
            sku=self.sku,
            name=self.name,
            brand=self.brand,
            category=self.category,
            material=self.material,
            price_band=self.price_band,
            geometry=self.geometry,
            parts=build_parts(self.category, self.width_cm, self.depth_cm, self.height_cm),
            score=round(score, 3),
            source="catalog",
        )


CATALOG: tuple[Sku, ...] = (
    # ---------- sofas ----------
    Sku(sku="SOFA-201", name="Kivik 2-seat sofa", brand="Kivik", category="sofa", material="fabric", price_band="$",
        width_cm=180, depth_cm=89, height_cm=83, aliases=("two seater", "loveseat", "couch")),
    Sku(sku="SOFA-301", name="Kivik 3-seat sofa", brand="Kivik", category="sofa", material="fabric", price_band="$$",
        width_cm=220, depth_cm=89, height_cm=83, aliases=("three seater", "couch")),
    Sku(sku="SOFA-302", name="Ektorp 3-seat sofa", brand="Ektorp", category="sofa", material="linen", price_band="$$",
        width_cm=218, depth_cm=95, height_cm=85, aliases=("three seater", "slipcover")),
    Sku(sku="SOFA-401", name="Soderhamn 4-seat sofa", brand="Soderhamn", category="sofa", material="fabric", price_band="$$$",
        width_cm=286, depth_cm=88, height_cm=83, aliases=("four seater", "couch")),
    Sku(sku="SOFA-L10", name="Kalltorp L-shaped sectional", brand="Kalltorp", category="sectional", material="fabric", price_band="$$$",
        width_cm=243, depth_cm=163, height_cm=86, clearance_cm=15, aliases=("corner sofa", "chaise", "l shape")),
    Sku(sku="SOFA-M01", name="Margret 2-seat sofa bed", brand="Margret", category="sofa", material="fabric", price_band="$$",
        width_cm=192, depth_cm=96, height_cm=88, aliases=("sofa bed", "futon")),
    Sku(sku="SOFA-S11", name="Sitskas modular 3-seat", brand="Sitskas", category="sofa", material="velour", price_band="$$$",
        width_cm=232, depth_cm=101, height_cm=78, aliases=("deep seat", "modular")),
    # ---------- armchairs ----------
    Sku(sku="CHR-101", name="Poang armchair", brand="Poang", category="armchair", material="birch", price_band="$",
        width_cm=72, depth_cm=77, height_cm=78, aliases=("birch chair", "lounge")),
    Sku(sku="CHR-102", name="Eames-style lounge chair", brand="Hovet", category="armchair", material="leather", price_band="$$$",
        width_cm=81, depth_cm=85, height_cm=81, clearance_cm=15, aliases=("wing chair", "reading chair")),
    Sku(sku="CHR-103", name="Strandmon wing armchair", brand="Strandmon", category="armchair", material="fabric", price_band="$$$",
        width_cm=110, depth_cm=105, height_cm=114, clearance_cm=15, aliases=("wing chair", "oversized")),
    Sku(sku="CHR-104", name="Loshi rocking chair", brand="Loshi", category="armchair", material="polyester", price_band="$",
        width_cm=66, depth_cm=68, height_cm=106, aliases=("rocking", "nursing")),
    Sku(sku="OTT-201", name="Klippan ottoman", brand="Klippan", category="ottoman", material="fabric", price_band="$",
        width_cm=61, depth_cm=61, height_cm=41, clearance_cm=5, aliases=("footstool", "pouffe")),
    # ---------- tables ----------
    Sku(sku="TAB-101", name="Ekenset dining table", brand="Ekenset", category="table", material="glass", price_band="$$",
        width_cm=85, depth_cm=85, height_cm=74, clearance_cm=75, aliases=("square table", "four seater table")),
    Sku(sku="TAB-102", name="Malsjelvi extending dining table", brand="Malsjelvi", category="table", material="oak veneer", price_band="$$$",
        width_cm=152, depth_cm=94, height_cm=75, clearance_cm=75, aliases=("extendable", "six seater table")),
    Sku(sku="TAB-103", name="Ingatorp 180 table", brand="Ingatorp", category="table", material="pine", price_band="$$",
        width_cm=180, depth_cm=80, height_cm=75, clearance_cm=80, aliases=("eight seater table", "long table")),
    Sku(sku="TAB-201", name="Lack side table", brand="Lack", category="table", material="particleboard", price_band="$",
        width_cm=55, depth_cm=55, height_cm=55, clearance_cm=10, aliases=("end table", "nightstand table")),
    Sku(sku="TAB-301", name="Stenheden coffee table", brand="Stenheden", category="table", material="oak", price_band="$",
        width_cm=90, depth_cm=55, height_cm=50, clearance_cm=30, aliases=("low table", "coffee")),
    Sku(sku="TAB-401", name="Burdet round dining table", brand="Burdet", category="table", material="birch", price_band="$$",
        width_cm=110, depth_cm=110, height_cm=74, clearance_cm=75, aliases=("round table",)),
    Sku(sku="DESK-101", name="Bektet desk with drawers", brand="Bektet", category="desk", material="birch", price_band="$$",
        width_cm=140, depth_cm=60, height_cm=75, clearance_cm=70, aliases=("writing desk", "study table")),
    Sku(sku="DESK-102", name="Uppspeel standing desk", brand="Uppspeel", category="desk", material="laminate", price_band="$$$",
        width_cm=160, depth_cm=80, height_cm=120, clearance_cm=70, aliases=("sit stand", "electric desk")),
    # ---------- storage ----------
    Sku(sku="BED-101", name="Malm double bed", brand="Malm", category="bed", material="particleboard", price_band="$$",
        width_cm=144, depth_cm=206, height_cm=100, clearance_cm=60, aliases=("four foot six", "queen bed")),
    Sku(sku="BED-102", name="Tarva king bed", brand="Tarva", category="bed", material="oak", price_band="$$$",
        width_cm=203, depth_cm=213, height_cm=110, clearance_cm=60, aliases=("super king", "five foot eighteen")),
    Sku(sku="BED-103", name="Slatthall single bed", brand="Slatthall", category="bed", material="pine", price_band="$",
        width_cm=97, depth_cm=209, height_cm=102, clearance_cm=50, aliases=("twin bed", "single")),
    Sku(sku="BED-104", name="Nemom raised bed frame", brand="Nemom", category="bed", material="oak veneer", price_band="$$",
        width_cm=125, depth_cm=213, height_cm=80, clearance_cm=50, aliases=("platform bed", "low frame")),
    Sku(sku="WRD-101", name="Pax wardrobe 100x58", brand="Pax", category="wardrobe", material="white stain", price_band="$$",
        width_cm=100, depth_cm=58, height_cm=201, clearance_cm=60, aliases=("two door", "sliding wardrobe")),
    Sku(sku="WRD-102", name="Pax wardrobe 200x58", brand="Pax", category="wardrobe", material="white stain", price_band="$$$",
        width_cm=200, depth_cm=58, height_cm=236, clearance_cm=60, aliases=("four door", "ceiling height")),
    Sku(sku="WRD-103", name="Brimnes wardrobe", brand="Brimnes", category="wardrobe", material="pine", price_band="$$",
        width_cm=140, depth_cm=57, height_cm=181, clearance_cm=60, aliases=("three door",)),
    Sku(sku="BCK-101", name="Billy bookcase", brand="Billy", category="bookcase", material="birch effect", price_band="$",
        width_cm=80, depth_cm=28, height_cm=202, clearance_cm=5, aliases=("shelf unit", "shelving")),
    Sku(sku="BCK-102", name="Eketorp narrow bookcase", brand="Eketorp", category="bookcase", material="oak", price_band="$$",
        width_cm=90, depth_cm=32, height_cm=200, clearance_cm=5, aliases=("shelf unit",)),
    Sku(sku="BCK-103", name="Kallax cube shelf 4x2", brand="Kallax", category="shelf", material="fiberboard", price_band="$",
        width_cm=77, depth_cm=39, height_cm=147, clearance_cm=5, aliases=("cube storage", "room divider")),
    Sku(sku="SBD-101", name="Herrevad sideboard", brand="Herrevad", category="sideboard", material="oak", price_band="$$$",
        width_cm=160, depth_cm=40, height_cm=90, clearance_cm=10, aliases=("credenza", "buffet")),
    Sku(sku="TVU-101", name="Besto TV bench", brand="Besto", category="tv unit", material="high gloss", price_band="$$",
        width_cm=180, depth_cm=40, height_cm=63, clearance_cm=10, aliases=("media unit", "tv stand")),
    Sku(sku="CAB-101", name="Helmer filing cabinet", brand="Helmer", category="cabinet", material="steel", price_band="$",
        width_cm=59, depth_cm=62, height_cm=125, clearance_cm=70, aliases=("drawers", "office cabinet")),
    Sku(sku="CAB-102", name="Rast nightstand", brand="Rast", category="cabinet", material="pine", price_band="$",
        width_cm=41, depth_cm=46, height_cm=68, clearance_cm=5, aliases=("bedside table", "nightstand")),
    # ---------- soft furnishing ----------
    Sku(sku="RUG-101", name="Rindar short-pile rug", brand="Rindar", category="rug", material="viscose", price_band="$$",
        width_cm=200, depth_cm=300, height_cm=1, clearance_cm=0, aliases=("large rug", "living room rug")),
    Sku(sku="STO-101", name="Alnatorp stool", brand="Alnatorp", category="stool", material="birch", price_band="$",
        width_cm=40, depth_cm=36, height_cm=44, clearance_cm=5, aliases=("step stool", "seat")),
)


def find(sku: str) -> Sku | None:
    return next((item for item in CATALOG if item.sku.upper() == sku.upper()), None)
