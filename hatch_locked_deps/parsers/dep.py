from dataclasses import dataclass


@dataclass(frozen=True)
class Dependency:
    name: str
    version: str
    markers: str | None = None

    def __str__(self) -> str:
        dep = f"{self.name}=={self.version}"
        if self.markers:
            dep += f" ; {self.markers}"
        return dep
