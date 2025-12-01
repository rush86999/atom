// Redirect to login
window.location.href = '/login';
return;
                }

// Get user's workspace
const userResponse = await fetch('/api/auth/me', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
});

if (!userResponse.ok) {
    window.location.href = '/login';
    return;
}

const user = await userResponse.json();

if (user.workspace_id) {
    // Fetch teams in workspace
    const teamsResponse = await fetch(`/api/enterprise/workspaces/${user.workspace_id}/teams`, {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (teamsResponse.ok) {
        const teamsData = await teamsResponse.json();
        setTeams(teamsData);
        if (teamsData.length > 0) {
            setSelectedTeamId(teamsData[0].id);
        }
    }
}
            } catch (error) {
    console.error('Failed to load teams:', error);
} finally {
    setLoading(false);
}
        };

loadTeams();
    }, []);

if (loading) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
    );
}

return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 py-8">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                        Team Collaboration
                    </h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-1">
                        Chat with your team in real-time
                    </p>
                </div>
                <button className="flex items-center space-x-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors">
                    <Plus className="w-5 h-5" />
                    <span>New Team</span>
                </button>
            </div>

            {teams.length === 0 ? (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center">
                    <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                        No Teams Yet
                    </h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-6">
                        Create your first team to start collaborating
                    </p>
                    <button className="px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors">
                        Create Team
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-12 gap-6">
                    {/* Team Sidebar */}
                    <div className="col-span-3">
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
                            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                                <h2 className="font-semibold text-gray-900 dark:text-white">
                                    Your Teams
                                </h2>
                            </div>
                            <div className="divide-y divide-gray-200 dark:divide-gray-700">
                                {teams.map((team) => (
                                    <button
                                        key={team.id}
                                        onClick={() => setSelectedTeamId(team.id)}
                                        className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors ${selectedTeamId === team.id ? 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500' : ''
                                            }`}
                                    >
                                        <div className="flex items-center space-x-3">
                                            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-semibold">
                                                {team.name[0].toUpperCase()}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium text-gray-900 dark:text-white truncate">
                                                    {team.name}
                                                </p>
                                                {team.description && (
                                                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                                                        {team.description}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Chat Panel */}
                    <div className="col-span-9">
                        {selectedTeamId ? (
                            <TeamChatPanel
                                teamId={selectedTeamId}
                                className="h-[calc(100vh-12rem)]"
                            />
                        ) : (
                            <div className="bg-white dark:bg-gray-800 rounded-lg shadow h-[calc(100vh-12rem)] flex items-center justify-center">
                                <p className="text-gray-500 dark:text-gray-400">
                                    Select a team to start chatting
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    </div>
);
}
