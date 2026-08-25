/**
 * OfficeCanvas Component
 *
 * Native viewer + editor for file-backed office canvases (.xlsx / .docx /
 * .pptx) presented by agents. Renders the structured snapshot served by
 * GET /api/canvas/{id} (content.format + sheets/text/slides) — mobile has no
 * canvas WebSocket subscription, so everything arrives via REST.
 *
 * Co-editing parity with web: when a canvasId and a bound file are present,
 * user edits commit to the real file via POST /api/v1/office/sync-update
 * (cell / document / slide / add_slide), and the response's fresh structured
 * snapshot re-renders the view. Without a binding the component is read-only.
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Badge, useTheme } from 'react-native-paper';
import { apiService } from '../../services/api';

export interface OfficeCanvasContent {
  format?: string; // 'xlsx' | 'docx' | 'pptx'
  office_file?: string;
  file_path?: string;
  html?: string;
  title?: string;
  // xlsx
  active_sheet?: string;
  sheet_names?: string[];
  sheets?: { name: string; rows: any[][] }[];
  formulas?: Record<string, Record<string, string>>;
  // docx
  text?: string;
  // pptx
  slides?: { slide_number: number; title: string; content: string }[];
}

interface OfficeCanvasProps {
  content: OfficeCanvasContent;
  /** Canvas id — when present (with a bound file), edits commit to the file. */
  canvasId?: string;
}

export function isOfficeContent(content: any): boolean {
  if (!content || typeof content !== 'object') return false;
  if (content.office_file) return true;
  return ['xlsx', 'docx', 'pptx'].includes(content.format);
}

export function OfficeCanvas({ content, canvasId }: OfficeCanvasProps) {
  const theme = useTheme();
  const format = (content.format ||
    (content.office_file || '').split('.').pop() ||
    '').toLowerCase();
  const fileName =
    content.title ||
    (content.office_file || content.file_path || '').split('/').pop() ||
    'Document';
  const filePath = content.office_file || content.file_path || '';
  const editable = !!(canvasId && filePath);

  // Local snapshot: server state + committed edits. Refreshed from the
  // sync-update response so recalced formula values round-trip like web.
  const [local, setLocal] = useState<OfficeCanvasContent>(content);
  const [docText, setDocText] = useState(content.text || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLocal(content);
    setDocText(content.text || '');
    setDirty(false);
  }, [content]);

  /**
   * Commit an edit to the bound file via /api/v1/office/sync-update and
   * apply the fresh structured snapshot the backend returns.
   */
  const commitEdit = async (
    editType: string,
    editData: Record<string, unknown>
  ) => {
    if (!editable) return;
    setError(null);
    setSaving(true);
    try {
      const res = await apiService.post<any>('/api/v1/office/sync-update', {
        canvas_id: canvasId,
        file_path: filePath,
        user_id: 'canvas_user', // server attributes from the auth token
        edit_type: editType,
        data: editData,
      });
      if (!res.success) {
        setError(res.error || 'Failed to save edit');
        return;
      }
      const snap = res.data?.content;
      if (snap?.format) {
        setLocal({ ...snap, file_path: filePath });
        if (editType === 'document') setDocText(snap.text ?? docText);
        setDirty(false);
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to save edit');
    } finally {
      setSaving(false);
    }
  };

  const initialSheet =
    local.sheets?.find((s) => s.name === local.active_sheet) ||
    local.sheets?.[0];
  const [activeSheetName, setActiveSheetName] = useState(
    initialSheet?.name || ''
  );

  const activeSheet = useMemo(
    () =>
      local.sheets?.find((s) => s.name === activeSheetName) ||
      local.sheets?.[0],
    [local.sheets, activeSheetName]
  );

  if (format === 'xlsx') {
    const rows = activeSheet?.rows || [];
    const colCount = rows.reduce((m, r) => Math.max(m, r?.length || 0), 0);
    return (
      <View style={styles.container}>
        <FileHeader
          fileName={fileName}
          format="Excel"
          theme={theme}
          saving={saving}
          error={error}
          editable={editable}
          dirty={dirty}
        />
        {(local.sheet_names?.length || 0) > 1 && (
          <View style={styles.sheetTabs}>
            {local.sheet_names!.map((name) => (
              <TouchableOpacity
                key={name}
                onPress={() => setActiveSheetName(name)}
                style={[
                  styles.sheetTab,
                  {
                    borderColor:
                      name === activeSheet?.name
                        ? theme.colors.primary
                        : theme.colors.outline,
                    backgroundColor:
                      name === activeSheet?.name
                        ? theme.colors.primaryContainer
                        : 'transparent',
                  },
                ]}
              >
                <Text
                  style={{
                    color:
                      name === activeSheet?.name
                        ? theme.colors.primary
                        : theme.colors.onSurfaceVariant,
                    fontSize: 12,
                    fontWeight: name === activeSheet?.name ? '700' : '400',
                  }}
                >
                  {name}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        <ScrollView horizontal showsHorizontalScrollIndicator>
          <View>
            {rows.map((row, rIdx) => (
              <View key={rIdx} style={styles.sheetRow}>
                {Array.from({ length: colCount }, (_, cIdx) => {
                  const coord = `${String.fromCharCode(65 + cIdx)}${rIdx + 1}`;
                  const value =
                    row?.[cIdx] == null ? '' : String(row[cIdx]);
                  const isFormula =
                    !!local.formulas?.[activeSheet?.name || '']?.[coord] ||
                    value.startsWith('=');
                  return (
                    <View
                      key={`${coord}:${value}`}
                      style={[
                        styles.sheetCell,
                        {
                          borderColor: theme.colors.outline,
                          backgroundColor: isFormula
                            ? theme.colors.secondaryContainer
                            : rIdx === 0
                            ? theme.colors.surfaceVariant
                            : 'transparent',
                        },
                      ]}
                    >
                      <TextInput
                        defaultValue={value}
                        editable={editable}
                        multiline
                        onEndEditing={(e) => {
                          const raw = e.nativeEvent.text ?? '';
                          if (raw !== value) {
                            commitEdit('cell', {
                              cell_path: `/${activeSheet?.name}/${coord}`,
                              value: raw,
                              is_formula: raw.startsWith('='),
                            });
                          }
                        }}
                        onChangeText={() => setDirty(true)}
                        style={{
                          color: theme.colors.onSurface,
                          fontSize: 12,
                          fontWeight: rIdx === 0 ? '700' : '400',
                          minWidth: 74,
                        }}
                      />
                    </View>
                  );
                })}
              </View>
            ))}
          </View>
        </ScrollView>
      </View>
    );
  }

  if (format === 'docx') {
    return (
      <View style={styles.container}>
        <FileHeader
          fileName={fileName}
          format="Word"
          theme={theme}
          saving={saving}
          error={error}
          editable={editable}
          dirty={dirty}
        />
        <Text style={{ color: theme.colors.onSurfaceVariant, fontSize: 11 }}>
          One line = one paragraph. Styles, tables and images are preserved on save.
        </Text>
        <TextInput
          value={docText}
          onChangeText={(t) => {
            setDocText(t);
            setDirty(true);
          }}
          onEndEditing={() => {
            if (editable && docText !== (local.text || '')) {
              commitEdit('document', { content: docText });
            }
          }}
          editable={editable}
          multiline
          textAlignVertical="top"
          style={[
            styles.docEditor,
            {
              borderColor: theme.colors.outline,
              color: theme.colors.onSurface,
            },
          ]}
        />
      </View>
    );
  }

  if (format === 'pptx') {
    return (
      <View style={styles.container}>
        <FileHeader
          fileName={fileName}
          format="PowerPoint"
          theme={theme}
          saving={saving}
          error={error}
          editable={editable}
          dirty={dirty}
        />
        {(local.slides || []).map((slide) => (
          <View
            key={slide.slide_number}
            style={[styles.slideCard, { borderColor: theme.colors.outline }]}
          >
            <View style={styles.slideHeader}>
              <Badge>{slide.slide_number}</Badge>
              <TextInput
                defaultValue={slide.title}
                key={`t:${slide.slide_number}:${slide.title}`}
                editable={editable}
                onEndEditing={(e) => {
                  const raw = e.nativeEvent.text ?? '';
                  if (raw !== slide.title) {
                    commitEdit('slide', {
                      slide_number: slide.slide_number,
                      title: raw,
                      content: slide.content,
                    });
                  }
                }}
                onChangeText={() => setDirty(true)}
                style={[styles.slideTitleInput, { color: theme.colors.onSurface }]}
                placeholder="Slide title"
              />
            </View>
            <TextInput
              defaultValue={slide.content}
              key={`c:${slide.slide_number}:${slide.content}`}
              editable={editable}
              multiline
              onEndEditing={(e) => {
                const raw = e.nativeEvent.text ?? '';
                if (raw !== slide.content) {
                  commitEdit('slide', {
                    slide_number: slide.slide_number,
                    title: slide.title,
                    content: raw,
                  });
                }
              }}
              onChangeText={() => setDirty(true)}
              textAlignVertical="top"
              style={{ color: theme.colors.onSurfaceVariant, fontSize: 13 }}
              placeholder="Slide content"
            />
          </View>
        ))}
        {editable && (
          <TouchableOpacity
            onPress={() =>
              commitEdit('add_slide', { title: 'New Slide', content: '' })
            }
            style={[styles.addSlideButton, { borderColor: theme.colors.outline }]}
          >
            <Text style={{ color: theme.colors.primary, fontSize: 12, fontWeight: '700' }}>
              + ADD SLIDE
            </Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={{ color: theme.colors.onSurfaceVariant }}>
        Unsupported office format: {format || 'unknown'}
      </Text>
    </View>
  );
}

function FileHeader({
  fileName,
  format,
  theme,
  saving,
  error,
  editable,
  dirty,
}: {
  fileName: string;
  format: string;
  theme: any;
  saving: boolean;
  error: string | null;
  editable: boolean;
  dirty: boolean;
}) {
  return (
    <View style={styles.fileHeader}>
      <View style={{ flexShrink: 1 }}>
        <Text style={[styles.fileName, { color: theme.colors.onSurface }]} numberOfLines={1}>
          {fileName}
        </Text>
        <Text style={{ color: theme.colors.onSurfaceVariant, fontSize: 10 }}>
          {error
            ? error
            : saving
            ? 'Saving…'
            : editable
            ? dirty
              ? 'Unsaved changes — blur a field to save'
              : 'Synced to file'
            : 'Read-only — ask the agent in chat to edit'}
        </Text>
      </View>
      {saving && <ActivityIndicator size="small" />}
      <Badge>{format}</Badge>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 12,
    gap: 8,
  },
  fileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  fileName: {
    fontSize: 14,
    fontWeight: '600',
    flexShrink: 1,
    marginRight: 8,
  },
  sheetTabs: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 4,
  },
  sheetTab: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
  },
  sheetRow: {
    flexDirection: 'row',
  },
  sheetCell: {
    minWidth: 90,
    maxWidth: 180,
    padding: 4,
    borderWidth: 0.5,
    justifyContent: 'center',
  },
  docEditor: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    lineHeight: 22,
    minHeight: 160,
  },
  slideCard: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
    gap: 8,
  },
  slideHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  slideTitleInput: {
    fontSize: 15,
    fontWeight: '600',
    flexShrink: 1,
    flex: 1,
  },
  addSlideButton: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
});

export default OfficeCanvas;
