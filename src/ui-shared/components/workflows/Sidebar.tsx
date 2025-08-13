import React from 'react';

export default ({ workflows, onLoadWorkflow, onTriggerWorkflow, onDeleteWorkflow }) => {
  const onDragStart = (event, nodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <aside style={{ borderRight: '1px solid #eee', padding: 15, fontSize: 12, width: 250 }}>
      <div>
        <div style={{ marginBottom: 10 }}>
          You can drag these nodes to the pane on the right.
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'googleCalendarCreateEvent')}
          draggable
        >
          Google Calendar: Create Event
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'gmailTrigger')}
          draggable
        >
          Gmail Trigger
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'googleCalendarTrigger')}
          draggable
        >
          Google Calendar Trigger
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'notionAction')}
          draggable
        >
          Notion Action
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'aiTask')}
          draggable
        >
          AI Task
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'delay')}
          draggable
        >
          Delay
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'llmFilter')}
          draggable
        >
          LLM Filter
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'reduce')}
          draggable
        >
          Combine
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'slackSendMessage')}
          draggable
        >
          Slack: Send Message
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'branch')}
          draggable
        >
          Branch
        </div>
        <div
          style={{
            border: '1px solid #ddd',
            padding: '10px 15px',
            borderRadius: '5px',
            marginBottom: 10,
            cursor: 'grab',
            textAlign: 'center'
          }}
          onDragStart={(event) => onDragStart(event, 'sendEmail')}
          draggable
        >
          Send Email
        </div>
      </div>
      <hr style={{ margin: '15px 0' }} />
      <div>
        <div style={{ marginBottom: 10 }}>Saved Workflows:</div>
        {workflows && workflows.map((wf) => (
          <div key={wf.id} style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
            <div
              onClick={() => onLoadWorkflow(wf)}
              style={{
                border: '1px solid #ddd',
                padding: '10px 15px',
                borderRadius: '5px',
                cursor: 'pointer',
                flex: 1,
              }}
            >
              {wf.name}
            </div>
            <button
              onClick={() => onTriggerWorkflow(wf.id)}
              style={{ marginLeft: 10 }}
            >
              Trigger
            </button>
            <button
              onClick={() => onDeleteWorkflow(wf.id)}
              style={{ marginLeft: 5, background: 'salmon', color: 'white', border: 'none', borderRadius: '3px', cursor: 'pointer' }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
};
