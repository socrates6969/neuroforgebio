// Response types of the operations that M3 had to hand-write (untyped `dict` routes). Since M4 (4.1)
// openapi/v1.yaml types them, so these are aliases of the generated schema types; the names stay so
// the views do not change.

import type {
  LineageOut,
  ProvEdgeOut,
  ProvNodeDetailOut,
  ProvNodeOut,
  WhoAmIOut,
  WindowJsonOut,
} from './generated';

export type Whoami = WhoAmIOut;
export type ProvNode = ProvNodeOut;
export type ProvKind = ProvNodeOut['kind'];
export type ProvEdge = ProvEdgeOut;
export type ProvRel = ProvEdgeOut['rel'];
export type LineageGraph = LineageOut;
export type NodeDetail = ProvNodeDetailOut;
/** `nf-window/1` JSON: header + data[channel][sample] in stored units (physical = v*scale+offset). */
export type SignalWindow = WindowJsonOut;
