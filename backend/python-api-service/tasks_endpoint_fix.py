    @app.route('/api/v1/tasks')
    def tasks_list():
        """List tasks from all services"""
        tasks = [
            {
                'id': 'task_github_1',
                'title': 'Review Pull Request',
                'description': 'Review and merge pending PR',
                'source': 'github',
                'priority': 'high',
                'status': 'pending',
                'due_date': '2025-11-03T18:00:00'
            },
            {
                'id': 'task_slack_1',
                'title': 'Team Meeting Notes',
                'description': 'Compile and send meeting notes',
                'source': 'slack',
                'priority': 'medium',
                'status': 'in_progress',
                'due_date': '2025-11-02T17:00:00'
            },
            {
                'id': 'task_google_1',
                'title': 'Prepare Presentation',
                'description': 'Create slides for client meeting',
                'source': 'google',
                'priority': 'high',
                'status': 'not_started',
                'due_date': '2025-11-05T12:00:00'
            }
        ]
        
        return jsonify({
            'tasks': tasks,
            'total': len(tasks),
            'by_priority': {
                'high': len([t for t in tasks if t['priority'] == 'high']),
                'medium': len([t for t in tasks if t['priority'] == 'medium']),
                'low': len([t for t in tasks if t['priority'] == 'low'])
            },
            'by_status': {
                'not_started': len([t for t in tasks if t['status'] == 'not_started']),
                'in_progress': len([t for t in tasks if t['status'] == 'in_progress']),
                'pending': len([t for t in tasks if t['status'] == 'pending']),
                'completed': len([t for t in tasks if t['status'] == 'completed'])
            },
            'success': True
        })