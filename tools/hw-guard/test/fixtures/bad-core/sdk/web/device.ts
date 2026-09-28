export async function pick() {
  return navigator.hid.requestDevice({ filters: [] });
}
