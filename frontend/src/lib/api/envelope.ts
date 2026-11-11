/** Success envelope used by every /api/v1 endpoint except health. */
export interface Envelope<T> {
  data: T;
  request_id: string;
}

export function unwrap<T>(envelope: Envelope<T>): T {
  return envelope.data;
}
