export type EventType = 'logon' | 'device' | 'file' | 'http' | 'email' | 'ldap';

export interface EventLog {
  id: string;
  timestamp: string;
  eventType: EventType;
  userId?: string;
  deviceId?: string;
  action: string;
  sourceFile?: string;
  sourceId?: string;
  rawDetail?: string;
}
