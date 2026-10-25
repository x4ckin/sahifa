/** Same rule as backend/sahifa/domain/lifecycle.py rooms_needed. */
export const BASE_IMAGES = 30;
export const BASE_VIDEOS = 5;
export const ROOM_IMAGES = 10;
export const ROOM_VIDEOS = 2;
export const MAX_EXTRA_ROOMS = 10;
export const MAX_IMAGES = BASE_IMAGES + MAX_EXTRA_ROOMS * ROOM_IMAGES; // 130
export const MAX_VIDEOS = BASE_VIDEOS + MAX_EXTRA_ROOMS * ROOM_VIDEOS; // 25

export function roomsNeeded(images: number, videos: number): number {
  const rooms = Math.max(
    Math.ceil((images - BASE_IMAGES) / ROOM_IMAGES),
    Math.ceil((videos - BASE_VIDEOS) / ROOM_VIDEOS),
    0,
  );
  if (rooms > MAX_EXTRA_ROOMS) throw new Error("media_full");
  return rooms;
}
