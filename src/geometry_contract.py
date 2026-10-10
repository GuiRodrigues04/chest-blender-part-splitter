"""Contrato formal de geometria e interfaces de corte para o Part Splitter.

Define as estruturas de dados padronizadas para resultados de corte (SplitResult)
e interfaces compartilhadas (CutInterface), garantindo execução determinística
e desacoplada em coordenadas de mundo (World Space).
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math
from mathutils import Vector, Matrix


@dataclass
class CutInterface:
    """Representa a interface geométrica compartilhada gerada pelo corte."""
    origin_world: Vector
    normal_a_to_b_world: Vector  # Aponta para fora da Parte A, entrando na Parte B
    axis_u_world: Vector         # Eixo U ortonormal no plano da interface (direção principal)
    axis_v_world: Vector         # Eixo V ortonormal no plano da interface (V = N x U)
    outer_contours_uv: List[List[Tuple[float, float]]] = field(default_factory=list)
    hole_contours_uv: List[List[Tuple[float, float]]] = field(default_factory=list)
    interface_triangles_world: List[Tuple[Vector, Vector, Vector]] = field(default_factory=list)
    is_planar: bool = True
    deviation_mm: float = 0.0
    source_mode: str = "PLANE"   # 'PLANE', 'LOOP', 'SOLID'
    width_mm: float = 0.0        # Dimensão útil ao longo do eixo maior (U)
    height_mm: float = 0.0       # Dimensão útil ao longo do eixo menor (V)
    area_mm2: float = 0.0

    def world_to_uv(self, point_world: Vector) -> Tuple[float, float]:
        """Projeta um ponto 3D de mundo no plano UV 2D da interface."""
        rel = point_world - self.origin_world
        u = rel.dot(self.axis_u_world)
        v = rel.dot(self.axis_v_world)
        return (u, v)

    def uv_to_world(self, u: float, v: float, offset_along_normal: float = 0.0) -> Vector:
        """Converte coordenadas UV 2D de volta para o espaço de mundo 3D."""
        return (
            self.origin_world
            + u * self.axis_u_world
            + v * self.axis_v_world
            + offset_along_normal * self.normal_a_to_b_world
        )


def build_cut_interface(
    origin_world: Vector,
    normal_a_to_b: Vector,
    boundary_points_world: List[Vector],
    interface_triangles: Optional[List[Tuple[Vector, Vector, Vector]]] = None,
    unit_scale: float = 1000.0,
    source_mode: str = "PLANE",
) -> CutInterface:
    """Constrói uma CutInterface formal com eixos principais (U=maior, V=menor) via PCA."""
    norm = normal_a_to_b.normalized()
    if norm.length < 1e-6:
        norm = Vector((0.0, 0.0, 1.0))

    if not boundary_points_world:
        ref = Vector((0.0, 0.0, 1.0)) if abs(norm.z) < 0.9 else Vector((0.0, 1.0, 0.0))
        u = norm.cross(ref).normalized()
        v = norm.cross(u).normalized()
        return CutInterface(
            origin_world=origin_world,
            normal_a_to_b_world=norm,
            axis_u_world=u,
            axis_v_world=v,
            is_planar=True,
            deviation_mm=0.0,
            source_mode=source_mode,
        )

    # Centroide dos pontos da borda
    centroid = sum(boundary_points_world, Vector()) / len(boundary_points_world)
    origin = origin_world if origin_world.length > 1e-6 else centroid

    # Base ortonormal inicial perpendicular à normal
    ref = Vector((0.0, 0.0, 1.0)) if abs(norm.z) < 0.9 else Vector((0.0, 1.0, 0.0))
    u_init = norm.cross(ref).normalized()
    v_init = norm.cross(u_init).normalized()

    # Projeção 2D dos pontos em relação ao centroide para análise de componentes principais (PCA)
    pts_2d = [
        ((p - centroid).dot(u_init), (p - centroid).dot(v_init))
        for p in boundary_points_world
    ]

    c_xx = sum(x * x for x, y in pts_2d)
    c_yy = sum(y * y for x, y in pts_2d)
    c_xy = sum(x * y for x, y in pts_2d)

    # Direção principal (ângulo theta no plano UV inicial)
    theta = 0.5 * math.atan2(2.0 * c_xy, c_xx - c_yy)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    axis_u = (cos_t * u_init + sin_t * v_init).normalized()
    axis_v = norm.cross(axis_u).normalized()

    # Mede extensões ao longo de U e V
    u_vals = [(p - origin).dot(axis_u) for p in boundary_points_world]
    v_vals = [(p - origin).dot(axis_v) for p in boundary_points_world]

    span_u = max(u_vals) - min(u_vals)
    span_v = max(v_vals) - min(v_vals)

    # Garante que axis_u seja o eixo de maior dimensão (maior comprimento útil)
    if span_u < span_v:
        axis_u, axis_v = axis_v, -axis_u
        u_vals, v_vals = v_vals, [-x for x in u_vals]
        span_u, span_v = span_v, span_u

    width_mm = span_u * unit_scale
    height_mm = span_v * unit_scale

    # Cálculo do desvio de planicidade
    dists = [abs((p - centroid).dot(norm)) for p in boundary_points_world]
    max_dev_bu = max(dists) if dists else 0.0
    dev_mm = max_dev_bu * unit_scale
    is_planar = dev_mm <= 0.1  # Tolerância de 0.1 mm

    # Polígono UV do contorno externo
    uv_contour = list(zip(u_vals, v_vals))

    # Área aproximada pelo polígono 2D
    area_bu = 0.0
    n_pts = len(uv_contour)
    if n_pts >= 3:
        for i in range(n_pts):
            x1, y1 = uv_contour[i]
            x2, y2 = uv_contour[(i + 1) % n_pts]
            area_bu += (x1 * y2 - x2 * y1)
        area_bu = 0.5 * abs(area_bu)
    area_mm2 = area_bu * (unit_scale ** 2)

    return CutInterface(
        origin_world=origin,
        normal_a_to_b_world=norm,
        axis_u_world=axis_u,
        axis_v_world=axis_v,
        outer_contours_uv=[uv_contour] if uv_contour else [],
        hole_contours_uv=[],
        interface_triangles_world=interface_triangles or [],
        is_planar=is_planar,
        deviation_mm=dev_mm,
        source_mode=source_mode,
        width_mm=width_mm,
        height_mm=height_mm,
        area_mm2=area_mm2,
    )


@dataclass
class SplitResult:
    """Resultado formal do corte de um modelo em duas peças."""
    part_a_metrics: Dict[str, Any] = field(default_factory=dict)
    part_b_metrics: Dict[str, Any] = field(default_factory=dict)
    interface: Optional[CutInterface] = None
    diagnostics_before_connectors: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str = ""

    def to_legacy_report(self) -> Dict[str, Any]:
        """Dicionário de compatibilidade com os testes e operadores legados."""
        return {
            "A": self.part_a_metrics,
            "B": self.part_b_metrics,
            "sum_volume_mm3": (
                self.part_a_metrics.get("volume_mm3", 0.0)
                + self.part_b_metrics.get("volume_mm3", 0.0)
            ),
            "interface": self.interface,
        }
