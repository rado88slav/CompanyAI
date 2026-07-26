export type ProviderDescriptor = {
  key: string;
  display_name: string;
  category: string;
  authentication_type: string;
  required_secret_fields: string[];
  optional_secret_fields: string[];
  configuration_fields: string[];
  capabilities: string[];
  credentials_may_expire: boolean;
};

export type ProviderConnection = {
  id: string;
  company_id: string;
  provider_key: string;
  display_name: string;
  slug: string;
  authentication_type: string;
  status: string;
  configuration: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  activated_at: string | null;
  deactivated_at: string | null;
  revoked_at: string | null;
};
