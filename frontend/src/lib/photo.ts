/** Longest side, in pixels, a photo is scaled down to before upload: enough to recognise a meal. */
const MAX_SIDE = 1024

/**
 * A photo as a JPEG data: URL no larger than `MAX_SIDE` on its longest side, so the upload is
 * small (typically 100–300 KB) whatever the camera took.
 */
export async function photoToDataUrl(file: File, maxSide = MAX_SIDE, quality = 0.8): Promise<string> {
  const bitmap = await createImageBitmap(file)
  try {
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement("canvas")
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    const context = canvas.getContext("2d")
    if (!context) throw new Error("This browser can't prepare the photo.")
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL("image/jpeg", quality)
  } finally {
    bitmap.close()
  }
}
