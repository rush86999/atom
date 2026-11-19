import React, { useEffect, useRef, useState } from 'react';
import TeamChatPanel from '../components/Teams/TeamChatPanel';

interface Team {
    id: string;
    name: string;
}

const readAuthToken = (): string | null => {
    if (typeof window === 'undefined') return null;
    try {
        return window.localStorage.getItem('auth_token');
    } catch {
        return null;
    }
};

const TeamChatPage = () => {
    const [authChecked, setAuthChecked] = useState(false);
    const [token, setToken] = useState<string | null>(null);
    const [teams, setTeams] = useState<Team[]>([]);
    const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [reloadKey, setReloadKey] = useState(0);
    const requestSeqRef = useRef(0);

    useEffect(() => {
        setToken(readAuthToken());
        setAuthChecked(true);
    }, []);

    // Load only the teams the signed-in user is allowed to see.
    useEffect(() => {
        if (!authChecked) return;

        if (!token) {
            setTeams([]);
            setSelectedTeamId(null);
            setLoading(false);
            setError(null);
            return;
        }

        const seq = ++requestSeqRef.current;
        let cancelled = false;
        const controller = new AbortController();

        setLoading(true);
        setError(null);

        fetch('/api/teams/mine', {
            headers: {
                Authorization: `Bearer ${token}`,
            },
            signal: controller.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error(`Teams request failed with ${response.status}`);
                }
                return response.json();
            })
            .then((data) => {
                if (cancelled || seq !== requestSeqRef.current) return;

                if (!Array.isArray(data)) {
                    throw new Error('Teams response was not an array');
                }

                const nextTeams: Team[] = data
                    .filter((team: unknown): team is { id: string; name?: unknown } => {
                        if (!team || typeof team !== 'object') return false;
                        const id = (team as { id?: unknown }).id;
                        return typeof id === 'string' && id.trim().length > 0;
                    })
                    .map((team) => ({
                        id: team.id,
                        name:
                            typeof team.name === 'string' && team.name.trim().length > 0
                                ? team.name
                                : team.id,
                    }));

                setTeams(nextTeams);
                // Never carry a selection that is no longer in the authorized
                // list. Fall back to the first available team.
                setSelectedTeamId((previous) =>
                    previous && nextTeams.some((team) => team.id === previous)
                        ? previous
                        : nextTeams[0]?.id ?? null
                );
                setLoading(false);
                setError(null);
            })
            .catch((loadError) => {
                if (
                    cancelled ||
                    controller.signal.aborted ||
                    seq !== requestSeqRef.current
                ) {
                    return;
                }
                console.error('Failed to load teams:', loadError);
                setTeams([]);
                setSelectedTeamId(null);
                setError('Could not load your teams.');
                setLoading(false);
            });

        return () => {
            cancelled = true;
            controller.abort();
        };
    }, [authChecked, token, reloadKey]);

    const selectedTeam = teams.find((team) => team.id === selectedTeamId) ?? null;

    const retry = () => {
        setReloadKey((value) => value + 1);
    };

    const selectTeam = (event: React.ChangeEvent<HTMLSelectElement>) => {
        const nextId = event.target.value;
        if (!teams.some((team) => team.id === nextId)) return;
        setSelectedTeamId(nextId);
    };

    return (
        <div className="p-8">
            <div className="mb-6">
                <h1 className="text-2xl font-bold">Team Chat</h1>
                <p className="mt-1 text-sm text-gray-600">
                    Chat with the members of a team you belong to.
                </p>
            </div>

            {!authChecked || (token && loading) ? (
                <div className="flex items-center gap-3 text-gray-600">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
                    <span>Loading teams...</span>
                </div>
            ) : !token ? (
                <div className="rounded-lg border border-gray-200 p-6">
                    <p className="text-gray-700">Please sign in to use Team Chat.</p>
                    <a
                        href="/login"
                        className="mt-3 inline-block px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                    >
                        Sign in
                    </a>
                </div>
            ) : error ? (
                <div className="rounded-lg border border-gray-200 p-6">
                    <p className="text-gray-700">{error}</p>
                    <button
                        type="button"
                        onClick={retry}
                        className="mt-3 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                    >
                        Retry
                    </button>
                </div>
            ) : teams.length === 0 ? (
                <div className="rounded-lg border border-gray-200 p-6">
                    <p className="text-gray-700">No teams available yet.</p>
                    <p className="mt-1 text-sm text-gray-500">
                        Join or create a team to start chatting.
                    </p>
                    <button
                        type="button"
                        onClick={retry}
                        className="mt-3 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                    >
                        Refresh
                    </button>
                </div>
            ) : (
                <div className="space-y-4">
                    <div>
                        <label
                            htmlFor="team-chat-team-picker"
                            className="block text-sm font-medium text-gray-700"
                        >
                            Team
                        </label>
                        <select
                            id="team-chat-team-picker"
                            value={selectedTeam?.id ?? ''}
                            onChange={selectTeam}
                            className="mt-1 w-full max-w-md rounded-lg border border-gray-300 bg-white px-3 py-2"
                        >
                            {teams.map((team) => (
                                <option key={team.id} value={team.id}>
                                    {team.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedTeam ? (
                        <div className="h-[calc(100vh-16rem)] min-h-[24rem]">
                            <TeamChatPanel
                                key={selectedTeam.id}
                                teamId={selectedTeam.id}
                            />
                        </div>
                    ) : (
                        <div className="rounded-lg border border-gray-200 p-6">
                            <p className="text-gray-700">Select a team to start chatting.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default TeamChatPage;
