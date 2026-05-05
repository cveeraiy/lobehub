'use client';

import { Skeleton } from 'antd';
import { useEffect, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';

import { authEnv } from '@/envs/auth';

import ConsentClientError from './ClientError';
import Consent from './Consent';
import Login from './Login';

interface InteractionData {
  clientId: string;
  clientMetadata: {
    clientName?: string;
    isFirstParty?: boolean;
    logo?: string;
  };
  error?: string;
  promptName: string;
  redirectUri: string;
  scopes: string[];
}

const InteractionPage = () => {
  const { uid } = useParams<{ uid: string }>();
  const [data, setData] = useState<InteractionData | null>(null);
  const [error, setError] = useState<{ message?: string; type?: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!uid) return;

    fetch(`/oidc/interaction?uid=${encodeURIComponent(uid)}`, { credentials: 'include' })
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok) {
          if (json.error === 'session_invalid') {
            setError({ type: 'session_invalid' });
          } else {
            setError({ message: json.message, type: 'server_error' });
          }
        } else if (json.error === 'unsupported_interaction') {
          setError({ message: json.promptName, type: 'unsupported_interaction' });
        } else {
          setData(json);
        }
      })
      .catch((err) => {
        console.error('Error fetching OIDC interaction:', err);
        setError({ message: err.message, type: 'fetch_error' });
      })
      .finally(() => setLoading(false));
  }, [uid]);

  if (!authEnv.ENABLE_OIDC) return <Navigate replace to="/" />;
  if (!uid) return <Navigate replace to="/" />;

  if (loading) return <Skeleton active />;

  if (error) {
    if (error.type === 'session_invalid') {
      return (
        <ConsentClientError
          error={{
            messageKey: 'consent.error.sessionInvalid.message',
            titleKey: 'consent.error.sessionInvalid.title',
          }}
        />
      );
    }

    if (error.type === 'unsupported_interaction') {
      return (
        <ConsentClientError
          error={{
            messageKey: 'consent.error.unsupportedInteraction.message',
            titleKey: 'consent.error.unsupportedInteraction.title',
            values: { promptName: error.message || '' },
          }}
        />
      );
    }

    return (
      <ConsentClientError
        error={{
          message: error.message,
          messageKey: error.message ? undefined : 'consent.error.unknown.message',
          titleKey: 'consent.error.title',
        }}
      />
    );
  }

  if (!data) return null;

  if (data.promptName === 'login') {
    return <Login clientMetadata={data.clientMetadata} uid={uid} />;
  }

  return (
    <Consent
      clientId={data.clientId}
      clientMetadata={data.clientMetadata}
      redirectUri={data.redirectUri}
      scopes={data.scopes}
      uid={uid}
    />
  );
};

export default InteractionPage;
