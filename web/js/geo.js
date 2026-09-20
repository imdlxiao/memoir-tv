/* Author: donglixiao · WGS84 validation and viewport clustering, without network access. */
export function validCoordinates(value) {
  return (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.keys(value).length === 2 &&
    typeof value.latitude === 'number' &&
    Number.isFinite(value.latitude) &&
    Math.abs(value.latitude) <= 90 &&
    typeof value.longitude === 'number' &&
    Number.isFinite(value.longitude) &&
    Math.abs(value.longitude) <= 180
  );
}
export const latLng = (item) => [item.coordinates.latitude, item.coordinates.longitude];
export function clusterPoints(items, project, radius = 88) {
  const groups = [],
    cells = new Map();
  for (const item of items) {
    const point = project(item),
      x = Math.floor(point.x / radius),
      y = Math.floor(point.y / radius);
    let group;
    for (let dx = -1; dx <= 1 && !group; dx++)
      for (let dy = -1; dy <= 1 && !group; dy++)
        group = (cells.get(`${x + dx}:${y + dy}`) || []).find(
          (g) => Math.hypot(g.point.x - point.x, g.point.y - point.y) < radius,
        );
    if (group) group.items.push(item);
    else {
      group = { point, items: [item] };
      groups.push(group);
      const key = `${x}:${y}`;
      if (!cells.has(key)) cells.set(key, []);
      cells.get(key).push(group);
    }
  }
  return groups;
}
