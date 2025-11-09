/**
 * Salesforce CRM Integration
 * Complete CRM platform with sales, service, marketing, and customer relationship management
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Container, Heading, Text, VStack, HStack, SimpleGrid,
  Card, CardBody, CardHeader, Divider, Button, ButtonGroup,
  Tab, TabList, TabPanels, TabPanel, Tabs, Badge, Alert,
  AlertIcon, AlertTitle, AlertDescription, Progress, Stat,
  StatLabel, StatNumber, StatHelpText, Icon, Select, Input,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter,
  ModalBody, ModalCloseButton, useDisclosure, FormControl,
  FormLabel, FormErrorMessage, Textarea, Checkbox, Switch,
  Spinner, Center, useToast, Accordion, AccordionItem,
  AccordionButton, AccordionPanel, AccordionIcon, Flex,
  Grid, GridItem, Link, Menu, MenuButton, MenuList,
  MenuItem, IconButton, Tag, TagLabel, TagCloseButton,
  List, ListItem, OrderedList, UnorderedList, Code,
  Tooltip, InputGroup, InputLeftElement, InputRightElement,
  NumberInput, NumberInputField, Stack, Wrap, WrapItem,
  Avatar, AvatarBadge, AvatarGroup, useColorModeValue,
  RangeSlider, RangeSliderThumb, RangeSliderTrack, RangeSliderFilledTrack,
  Textarea as ChakraTextarea, RadioGroup, Radio, RadioGroup as ChakraRadioGroup,
  CheckboxGroup, HStack as ChakraHStack, VStack as ChakraVStack,
  chakra, Portal, Popover, PopoverTrigger, PopoverContent,
  PopoverArrow, PopoverHeader, PopoverBody, PopoverCloseButton
} from '@chakra-ui/react';
import {
  FiDatabase, FiUsers, FiTarget, FiDollarSign, FiPhone,
  FiMail, FiMessageSquare, FiCalendar, FiFile, FiSettings,
  FiTrendingUp, FiBarChart, FiPieChart, FiActivity,
  FiCheck, FiX, FiEdit, FiTrash, FiPlus, FiSearch,
  FiFilter, FiDownload, FiUpload, FiRefreshCw, FiEye,
  FiEyeOff, FiLock, FiUnlock, FiUser, FiBriefcase,
  FiPackage, FiShoppingCart, FiCreditCard, FiDollarSign,
  FiTrendingDown, FiAlertCircle, FiCheckCircle, FiXCircle,
  FiInfo, FiHelpCircle, FiHome, FiGrid, FiList,
  FiRepeat, FiCpu, FiServer, FiCloud, FiBell,
  FiShield, FiKey, FiClock, FiMapPin, FiLink,
  FiExternalLink, FiArchive, FiFlag, FiTag, FiStar,
  FiBookmark, FiHeart, FiShare, FiCopy, FiMove,
  FiChevronRight, FiChevronDown, FiChevronUp, FiChevronLeft,
  FiMoreVertical, FiMoreHorizontal, FiMenu, FiSidebar,
  FiColumns, FiMaximize, FiMinimize, FiExpand, FiShrink,
  FiZoomIn, FiZoomOut, FiRotateCw, FiCorners, FiCrop,
  FiEdit2, FiLayers, FiFolder, FiFolderOpen, FiImage,
  FiVideo, FiMic, FiCamera, FiHeadphones, FiWifi,
  FiWifiOff, FiBattery, FiBatteryCharging, FiSmartphone,
  FiTablet, FiMonitor, FiTv, FiRadio, FiSpeaker,
  FiSpeakerOff, FiVolume, FiVolume1, FiVolume2,
  FiVolumeX, FiPause, FiPlay, FiSkipBack, FiSkipForward,
  FiRepeat, FiShuffle, FiFastForward, FiRewind,
  FiStop, FiRecord, FiSave, FiPrinter, FiScan,
  FiShare2, FiSend, FiPaperclip, FiImage, FiVideo
} from 'react-icons/fi';
import { toast } from 'react-hot-toast';

// Types
export interface SalesforceUser {
  id: string;
  username: string;
  email: string;
  name: string;
  firstName: string;
  lastName: string;
  title: string;
  phone: string;
  mobilePhone: string;
  fax: string;
  street: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
  locale: string;
  timezone: string;
  active: boolean;
  lastLoginDate: string;
  userType: string;
  profilePhotoUrl: string;
  userRoleId: string;
  userRoleName: string;
  teamId: string;
  teamName: string;
  division: string;
  department: string;
  reportsToId: string;
  managerName: string;
  emailPreferencesAutoBcc: string;
  emailPreferencesStayInTouch: boolean;
  emailPreferencesIndividuals: boolean;
  emailPreferencesAnnouncements: boolean;
  emailPreferencesCommunity: boolean;
  emailPermissionsOrgWideEmail: boolean;
  emailPermissionsProvision: boolean;
  emailPermissionsRelease: boolean;
  emailPermissionsUserInformation: boolean;
  emailPermissionsDataManagement: boolean;
  createdDate: string;
  modifiedDate: string;
}

export interface SalesforceAccount {
  id: string;
  name: string;
  type: string;
  billingStreet: string;
  billingCity: string;
  billingState: string;
  billingPostalCode: string;
  billingCountry: string;
  shippingStreet: string;
  shippingCity: string;
  shippingState: string;
  shippingPostalCode: string;
  shippingCountry: string;
  phone: string;
  fax: string;
  website: string;
  industry: string;
  annualRevenue: number;
  numberOfEmployees: number;
  description: string;
  tickerSymbol: string;
  ownership: string;
  rating: string;
  sicCode: string;
  site: string;
  createdDate: string;
  lastActivityDate: string;
  lastViewedDate: string;
  jigsawCompanyId: string;
  cleanStatus: string;
  accountSource: string;
  dunsNumber: string;
  tradestyle: string;
  naicsCode: string;
  naicsDesc: string;
  yearStarted: string;
  sicDesc: string;
  dunsPrimaryName: string;
  dunsControlNumber: string;
  dunsControlCode: string;
}

export interface SalesforceContact {
  id: string;
  accountId: string;
  firstName: string;
  lastName: string;
  email: string;
  title: string;
  phone: string;
  mobilePhone: string;
  homePhone: string;
  otherPhone: string;
  fax: string;
  mailingStreet: string;
  mailingCity: string;
  mailingState: string;
  mailingPostalCode: string;
  mailingCountry: string;
  otherStreet: string;
  otherCity: string;
  otherState: string;
  otherPostalCode: string;
  otherCountry: string;
  department: string;
  leadSource: string;
  birthdate: string;
  description: string;
  assistantName: string;
  assistantPhone: string;
  reportsToId: string;
  emailBouncedDate: string;
  emailBouncedReason: string;
  individualId: string;
  isEmailBounced: boolean;
  createdDate: string;
  lastModifiedDate: string;
  lastCURequestDate: string;
  lastCUUpdateDate: string;
  lastActivityDate: string;
  lastViewedDate: string;
  jigsawContactId: string;
  jigsawAccountId: string;
  cleanStatus: string;
  accountRecordId: string;
  ownerRecordId: string;
  contactRecordId: string;
  reportsToRecordId: string;
  assistantRecordId: string;
  photoUrl: string;
  optOutEmail: boolean;
  optOutFax: boolean;
  optOutPhone: boolean;
  optOutMobilePhone: boolean;
  optOutOtherPhone: boolean;
  optOutEmailPersonal: boolean;
  optOutEmailWork: boolean;
  optOutEmailBoth: boolean;
  doNotCall: boolean;
  hasOptedOutOfEmail: boolean;
  hasOptedOutOfFax: boolean;
  hasOptedOutOfPhone: boolean;
  hasOptedOutOfMobilePhone: boolean;
  hasOptedOutOfOtherPhone: boolean;
  hasOptedOutOfEmailPersonal: boolean;
  hasOptedOutOfEmailWork: boolean;
  hasOptedOutOfEmailBoth: boolean;
  allowMassEmailOptOut: boolean;
  personalEmailGmailCom: boolean;
  personalEmailOutlookCom: boolean;
  personalEmailYahooCom: boolean;
  personalEmailAolCom: boolean;
  personalEmailOther: boolean;
}

export interface SalesforceLead {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  title: string;
  phone: string;
  mobilePhone: string;
  company: string;
  street: string;
  city: string;
  state: string;
  postalCode: string;
  country: string;
  industry: string;
  annualRevenue: number;
  numberOfEmployees: number;
  description: string;
  rating: string;
  status: string;
  leadSource: string;
  convertedAccountId: string;
  convertedContactId: string;
  convertedDate: string;
  convertedOpportunityId: string;
  isConverted: boolean;
  isUnreadByOwner: boolean;
  createdDate: string;
  lastModifiedDate: string;
  lastViewedDate: string;
  lastActivityDate: string;
  jigsawCompanyId: string;
  leadSourceDescription: string;
  address: string;
  website: string;
  latitude: string;
  longitude: string;
  geocodeAccuracy: string;
  emailBouncedDate: string;
  emailBouncedReason: string;
  individualId: string;
  isEmailBounced: boolean;
  dunsNumber: string;
  tradestyle: string;
  naicsCode: string;
  naicsDesc: string;
  yearStarted: string;
  sicDesc: string;
  dunsPrimaryName: string;
  dunsControlNumber: string;
  dunsControlCode: string;
  primaryAddressCountryCode: string;
  primaryAddressStateCode: string;
  primaryAddressCity: string;
  primaryAddressPostalCode: string;
  primaryAddressStreet: string;
  optOutEmail: boolean;
  optOutFax: boolean;
  optOutPhone: boolean;
  optOutMobilePhone: boolean;
  optOutOtherPhone: boolean;
  optOutEmailPersonal: boolean;
  optOutEmailWork: boolean;
  optOutEmailBoth: boolean;
  allowMassEmailOptOut: boolean;
  hasOptedOutOfEmail: boolean;
  hasOptedOutOfFax: boolean;
  hasOptedOutOfPhone: boolean;
  hasOptedOutOfMobilePhone: boolean;
  hasOptedOutOfOtherPhone: boolean;
  hasOptedOutOfEmailPersonal: boolean;
  hasOptedOutOfEmailWork: boolean;
  hasOptedOutOfEmailBoth: boolean;
  doNotCall: boolean;
  personalEmailGmailCom: boolean;
  personalEmailOutlookCom: boolean;
  personalEmailYahooCom: boolean;
  personalEmailAolCom: boolean;
  personalEmailOther: boolean;
  leadScore: number;
  emailScore: number;
  phoneScore: number;
  leadScoreReasons: string[];
  emailScoreReasons: string[];
  phoneScoreReasons: string[];
  digitalFootprint: string;
  digitalFootprintDate: string;
  emailProvider: string;
  emailDomain: string;
  emailSuffix: string;
  emailFormat: string;
  emailTypo: boolean;
  phoneInvalid: boolean;
  phoneInvalidReason: string;
  phoneScore: number;
  phoneScoreReasons: string[];
  leadScoreModel: string;
  leadScoreVersion: string;
  leadScoreUpdatedDate: string;
  leadScoreReasons: string;
  leadScoreReasonsDetails: string;
  leadScoreReasonsDetailsCount: number;
  leadScoreReasonsDetailsMaxCount: number;
  leadScoreReasonsDetailsThreshold: number;
  leadScoreReasonsDetailsWeight: number;
  leadScoreReasonsDetailsType: string;
  leadScoreReasonsDetailsRuleId: string;
  leadScoreReasonsDetailsRuleName: string;
  leadScoreReasonsDetailsRuleDescription: string;
  leadScoreReasonsDetailsRuleActive: boolean;
  leadScoreReasonsDetailsRuleType: string;
  leadScoreReasonsDetailsRulePriority: number;
  leadScoreReasonsDetailsRuleField: string;
  leadScoreReasonsDetailsRuleOperator: string;
  leadScoreReasonsDetailsRuleValue: string;
  leadScoreReasonsDetailsRuleValueType: string;
  leadScoreReasonsDetailsRuleValueMin: number;
  leadScoreReasonsDetailsRuleValueMax: number;
  leadScoreReasonsDetailsRuleValueUnit: string;
  leadScoreReasonsDetailsRuleValueCurrency: string;
  leadScoreReasonsDetailsRuleValueDate: string;
  leadScoreReasonsDetailsRuleValueDateTime: string;
  leadScoreReasonsDetailsRuleValueBoolean: boolean;
  leadScoreReasonsDetailsRuleValueLookup: string;
  leadScoreReasonsDetailsRuleValueMultiSelect: string[];
  leadScoreReasonsDetailsRuleValueReference: string;
  leadScoreReasonsDetailsRuleValueReferenceId: string;
  leadScoreReasonsDetailsRuleValueReferenceName: string;
  leadScoreReasonsDetailsRuleValueReferenceRecordId: string;
  leadScoreReasonsDetailsRuleValueReferenceRecordName: string;
  leadScoreReasonsDetailsRuleValueReferenceRecordType: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordId: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordName: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordType: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordId: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordName: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordType: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFields: string[];
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldId: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldName: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldType: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldRequired: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldDefault: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldDescription: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldFormula: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldHelpText: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldTooltip: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookup: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupField: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupFieldType: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupRequired: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupDefault: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupDescription: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupFormula: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupHelpText: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupTooltip: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupAutoNumber: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupNumberFormat: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupCurrency: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupDecimal: number;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupEmail: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupLength: number;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupPercent: number;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupPhone: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupPicklist: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupPicklistValues: string[];
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupText: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupTextArea: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupUrl: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsFilter: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsSortable: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsUpdatable: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsCreateable: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsNillable: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsUnique: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsDefaultedOnCreate: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupIsDependentPicklist: boolean;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupControllerName: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupDefaultValue: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupValue: string;
  leadScoreReasonsDetailsRuleValueReferenceTargetRecordTypeFieldLookupVisualforceFieldNames: string[];
}

export interface SalesforceOpportunity {
  id: string;
  name: string;
  accountId: string;
  accountName: string;
  type: string;
  leadSource: string;
  amount: number;
  currencyIsoCode: string;
  closeDate: string;
  expectedRevenue: number;
  probability: number;
  stageName: string;
  isClosed: boolean;
  isWon: boolean;
  isLost: boolean;
  forecastCategory: string;
  description: string;
  nextStep: string;
  campaignId: string;
  campaignName: string;
  primaryCampaignSource: string;
  ownerId: string;
  ownerName: string;
  createdDate: string;
  lastModifiedDate: string;
  lastActivityDate: string;
  lastViewedDate: string;
  fiscal: string;
  fiscalQuarter: number;
  fiscalYear: number;
  syncQuote: boolean;
  quoteId: string;
  quoteName: string;
  quoteNumber: string;
  quoteStatus: string;
  quoteTotalPrice: number;
  quoteGrandTotalPrice: number;
  quoteDiscount: number;
  quoteSubtotal: number;
  quoteTax: number;
  quoteShippingHandling: number;
  quoteBillingStreet: string;
  quoteBillingCity: string;
  quoteBillingState: string;
  quoteBillingPostalCode: string;
  quoteBillingCountry: string;
  quoteShippingStreet: string;
  quoteShippingCity: string;
  quoteShippingState: string;
  quoteShippingPostalCode: string;
  quoteShippingCountry: string;
  quoteContactId: string;
  quoteContactName: string;
  quoteContactEmail: string;
  quoteContactPhone: string;
  quoteExpirationDate: string;
  quoteDescription: string;
  quoteAdditionalDescription: string;
  quoteTerms: string;
  quoteCustomerType: string;
  quoteCustomerSize: string;
  quoteCustomerIndustry: string;
  quoteCustomerRevenue: number;
  quoteCustomerEmployees: number;
  quoteCustomerLocation: string;
  quoteCustomerComments: string;
  quoteCustomerRating: string;
  quoteCustomerAccountType: string;
  quoteCustomerAccountTypeOther: string;
  quoteCustomerAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
}

export interface SalesforceCase {
  id: string;
  caseNumber: string;
  contactId: string;
  contactName: string;
  accountId: string;
  accountName: string;
  type: string;
  status: string;
  reason: string;
  origin: string;
  subject: string;
  description: string;
  priority: string;
  severity: string;
  escalation: string;
  escalationReason: string;
  escalatedBy: string;
  escalatedDate: string;
  closedDate: string;
  isClosed: boolean;
  isEscalated: boolean;
  hasUnreadReplies: boolean;
  hasAttachment: boolean;
  createdDate: string;
  lastModifiedDate: string;
  lastViewedDate: string;
  lastActivityDate: string;
  ownerId: string;
  ownerName: string;
  contactEmail: string;
  contactPhone: string;
  contactMobilePhone: string;
  contactTitle: string;
  contactDepartment: string;
  contactLeadSource: string;
  contactStreet: string;
  contactCity: string;
  contactState: string;
  contactPostalCode: string;
  contactCountry: string;
  productInterest: string;
  productDetails: string;
  productCategory: string;
  productIssue: string;
  productSubIssue: string;
  productVersion: string;
  productBuild: string;
  productQuantity: number;
  productUnitPrice: number;
  productTotalPrice: number;
  productDiscount: number;
  productSubtotal: number;
  productTax: number;
  productShippingHandling: number;
  productGrandTotalPrice: number;
  productBillingStreet: string;
  productBillingCity: string;
  productBillingState: string;
  productBillingPostalCode: string;
  productBillingCountry: string;
  productShippingStreet: string;
  productShippingCity: string;
  productShippingState: string;
  productShippingPostalCode: string;
  productShippingCountry: string;
  productContactId: string;
  productContactName: string;
  productContactEmail: string;
  productContactPhone: string;
  productContactTitle: string;
  productContactDepartment: string;
  productContactLeadSource: string;
  productContactStreet: string;
  productContactCity: string;
  productContactState: string;
  productContactPostalCode: string;
  productContactCountry: string;
  productComments: string;
  productCustomerType: string;
  productCustomerSize: string;
  productCustomerIndustry: string;
  productCustomerRevenue: number;
  productCustomerEmployees: number;
  productCustomerLocation: string;
  productCustomerComments: string;
  productCustomerRating: string;
  productCustomerAccountType: string;
  productCustomerAccountTypeOther: string;
  productCustomerAccountTypeOtherDescription: string;
  productCustomerAccountTypeOtherIndustry: string;
  productCustomerAccountTypeOtherIndustryDescription: string;
  productCustomerAccountTypeOtherRevenue: number;
  productCustomerAccountTypeOtherEmployees: number;
  productCustomerAccountTypeOtherLocation: string;
  productCustomerAccountTypeOtherComments: string;
  productCustomerAccountTypeOtherRating: string;
  productCustomerAccountTypeOtherAccountTypeOther: string;
  productCustomerAccountTypeOtherAccountTypeOtherDescription: string;
  productCustomerAccountTypeOtherAccountTypeOtherIndustry: string;
  productCustomerAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  productCustomerAccountTypeOtherAccountTypeOtherRevenue: number;
  productCustomerAccountTypeOtherAccountTypeOtherEmployees: number;
  productCustomerAccountTypeOtherAccountTypeOtherLocation: string;
  productCustomerAccountTypeOtherAccountTypeOtherComments: string;
  productCustomerAccountTypeOtherAccountTypeOtherRating: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOther: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherDescription: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustry: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherIndustryDescription: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherRevenue: number;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherEmployees: number;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherLocation: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherComments: string;
  productCustomerAccountTypeOtherAccountTypeOtherAccountTypeOtherRating: string;
}

export interface SalesforceCampaign {
  id: string;
  name: string;
  type: string;
  status: string;
  startDate: string;
  endDate: string;
  description: string;
  budgetedCost: number;
  actualCost: number;
  expectedRevenue: number;
  expectedResponse: number;
  numberSent: number;
  numberResponses: number;
  isActive: boolean;
  parentId: string;
  parentName: string;
  memberStatus: string;
  numberConverted: number;
  numberWon: number;
  numberLeads: number;
  numberContacts: string;
  numberAccounts: string;
  numberOpportunities: string;
  ownerRecordId: string;
  ownerName: string;
  createdDate: string;
  lastModifiedDate: string;
  lastViewedDate: string;
  lastActivityDate: string;
  fiscal: string;
  fiscalQuarter: number;
  fiscalYear: number;
  syncQuote: boolean;
  quoteId: string;
  quoteName: string;
  quoteNumber: string;
  quoteStatus: string;
  quoteTotalPrice: number;
  quoteGrandTotalPrice: number;
  quoteDiscount: number;
  quoteSubtotal: number;
  quoteTax: number;
  quoteShippingHandling: number;
  quoteBillingStreet: string;
  quoteBillingCity: string;
  quoteBillingState: string;
  quoteBillingPostalCode: string;
  quoteBillingCountry: string;
  quoteShippingStreet: string;
  quoteShippingCity: string;
  quoteShippingState: string;
  quoteShippingPostalCode: string;
  quoteShippingCountry: string;
  quoteContactId: string;
  quoteContactName: string;
  quoteContactEmail: string;
  quoteContactPhone: string;
  quoteContactTitle: string;
  quoteContactDepartment: string;
  quoteContactLeadSource: string;
  quoteContactStreet: string;
  quoteContactCity: string;
  quoteContactState: string;
  quoteContactPostalCode: string;
  quoteContactCountry: string;
  quoteComments: string;
  quoteCustomerType: string;
  quoteCustomerSize: string;
  quoteCustomerIndustry: string;
  quoteCustomerRevenue: number;
  quoteCustomerEmployees: number;
  quoteCustomerLocation: string;
  quoteCustomerComments: string;
  quoteCustomerRating: string;
  quoteCustomerAccountType: string;
  quoteCustomerAccountTypeOther: string;
  quoteCustomerAccountTypeOtherDescription: string;
  quoteCustomerAccountTypeOtherIndustry: string;
  quoteCustomerAccountTypeOtherIndustryDescription: string;
  quoteCustomerAccountTypeOtherRevenue: number;
  quoteCustomerAccountTypeOtherEmployees: number;
  quoteCustomerAccountTypeOtherLocation: string;
  quoteCustomerAccountTypeOtherComments: string;
  quoteCustomerAccountTypeOtherRating: string;
}

export interface SalesforceConfig {
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  environment: 'sandbox' | 'production';
  apiVersion: string;
  timeout: number;
  maxRetries: number;
}

// Main Component Interface
export interface SalesforceManagerProps {
  config?: Partial<SalesforceConfig>;
  onError?: (error: Error) => void;
  onSuccess?: (message: string) => void;
  theme?: 'light' | 'dark';
  compact?: boolean;
}

// Main Component
export const SalesforceManager: React.FC<SalesforceManagerProps> = ({
  config,
  onError,
  onSuccess,
  theme = 'light',
  compact = false
}) => {
  // State Management
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Data State
  const [users, setUsers] = useState<SalesforceUser[]>([]);
  const [accounts, setAccounts] = useState<SalesforceAccount[]>([]);
  const [contacts, setContacts] = useState<SalesforceContact[]>([]);
  const [leads, setLeads] = useState<SalesforceLead[]>([]);
  const [opportunities, setOpportunities] = useState<SalesforceOpportunity[]>([]);
  const [cases, setCases] = useState<SalesforceCase[]>([]);
  const [campaigns, setCampaigns] = useState<SalesforceCampaign[]>([]);
  
  // Modal State
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [modalMode, setModalMode] = useState<'create' | 'edit' | 'view'>('view');
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [detailsModalOpen, setDetailsModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  
  // Form State
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [configData, setConfigData] = useState<SalesforceConfig>({
    clientId: config?.clientId || '',
    clientSecret: config?.clientSecret || '',
    redirectUri: config?.redirectUri || '',
    environment: config?.environment || 'sandbox',
    apiVersion: config?.apiVersion || '56.0',
    timeout: config?.timeout || 30000,
    maxRetries: config?.maxRetries || 3
  });
  
  // Filter State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedOwner, setSelectedOwner] = useState<string>('');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [dateRange, setDateRange] = useState<{ start: string; end: string }>({
    start: '',
    end: ''
  });
  
  // Toast
  const toast = useToast();

  // API Base URL
  const API_BASE_URL = '/api/salesforce';

  // Initialize Component
  useEffect(() => {
    checkConnection();
  }, []);

  // Check Connection Status
  const checkConnection = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/status`);
      const data = await response.json();
      setIsConnected(data.authenticated);
    } catch (error) {
      setIsConnected(false);
    }
  }, []);

  // Connect to Salesforce
  const handleConnect = useCallback(async () => {
    setIsConnecting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/integration/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: configData })
      });
      const data = await response.json();
      
      if (data.success) {
        setIsConnected(true);
        setConfigModalOpen(false);
        onSuccess?.('Salesforce connected successfully');
        toast({
          title: 'Connection Successful',
          description: 'Salesforce has been connected successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        // Load initial data
        loadDashboardData();
      } else {
        throw new Error(data.error || 'Connection failed');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: error.message || 'Failed to connect to Salesforce',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsConnecting(false);
    }
  }, [configData, onError, onSuccess, toast]);

  // Load Dashboard Data
  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [usersData, accountsData, contactsData, opportunitiesData, casesData] = await Promise.all([
        fetch(`${API_BASE_URL}/users`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/accounts`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/contacts`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/opportunities`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/cases`).then(r => r.json().then(d => d.success ? d.data : []))
      ]);
      
      setUsers(usersData);
      setAccounts(accountsData);
      setContacts(contactsData);
      setOpportunities(opportunitiesData);
      setCases(casesData);
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Handle configuration updates
  const handleConfigUpdate = async (newConfig: Partial<SalesforceConfig>) => {
    try {
      const response = await fetch(`${API_BASE_URL}/config/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      const data = await response.json();
      
      if (data.success) {
        setConfigData(prev => ({ ...prev, ...newConfig }));
        onSuccess?.('Configuration updated successfully');
        toast({
          title: 'Configuration Updated',
          description: 'Salesforce configuration updated successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error(data.error || 'Failed to update configuration');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Update Failed',
        description: error.message || 'Failed to update configuration',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Filter Data
  const filteredAccounts = useMemo(() => {
    let filtered = accounts;
    
    if (searchTerm) {
      filtered = filtered.filter(account => 
        account.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (selectedOwner) {
      filtered = filtered.filter(account => 
        account.ownerId === selectedOwner
      );
    }
    
    return filtered;
  }, [accounts, searchTerm, selectedOwner]);

  const filteredContacts = useMemo(() => {
    let filtered = contacts;
    
    if (searchTerm) {
      filtered = filtered.filter(contact => 
        `${contact.firstName} ${contact.lastName}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
        contact.email.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (selectedOwner) {
      filtered = filtered.filter(contact => 
        contact.ownerId === selectedOwner
      );
    }
    
    return filtered;
  }, [contacts, searchTerm, selectedOwner]);

  const filteredOpportunities = useMemo(() => {
    let filtered = opportunities;
    
    if (searchTerm) {
      filtered = filtered.filter(opportunity => 
        opportunity.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (selectedStatus && selectedStatus !== 'all') {
      filtered = filtered.filter(opportunity => 
        opportunity.stageName === selectedStatus
      );
    }
    
    if (selectedOwner) {
      filtered = filtered.filter(opportunity => 
        opportunity.ownerId === selectedOwner
      );
    }
    
    return filtered;
  }, [opportunities, searchTerm, selectedStatus, selectedOwner]);

  const filteredCases = useMemo(() => {
    let filtered = cases;
    
    if (searchTerm) {
      filtered = filtered.filter(case_ => 
        case_.subject.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (selectedStatus && selectedStatus !== 'all') {
      filtered = filtered.filter(case_ => 
        case_.status === selectedStatus
      );
    }
    
    if (selectedPriority && selectedPriority !== 'all') {
      filtered = filtered.filter(case_ => 
        case_.priority === selectedPriority
      );
    }
    
    if (selectedOwner) {
      filtered = filtered.filter(case_ => 
        case_.ownerId === selectedOwner
      );
    }
    
    return filtered;
  }, [cases, searchTerm, selectedStatus, selectedPriority, selectedOwner]);

  // Format Date
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const formatCurrency = (amount: number, currency: string = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  // Get Status Color
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      all: 'gray',
      open: 'blue',
      closed: 'green',
      pending: 'orange',
      escalated: 'red',
      working: 'yellow',
      completed: 'green',
      new: 'purple',
      responded: 'blue',
      rejected: 'red',
      accepted: 'green'
    };
    return colors[status] || 'gray';
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      all: 'gray',
      high: 'red',
      medium: 'orange',
      low: 'green',
      urgent: 'red',
      normal: 'blue',
      low: 'green'
    };
    return colors[priority] || 'gray';
  };

  // Render Connection Status
  const renderConnectionStatus = () => (
    <Alert status={isConnected ? 'success' : 'warning'} mb={4}>
      <AlertIcon as={isConnected ? FiCheckCircle : FiAlertCircle} />
      <Box flex="1">
        <AlertTitle>{isConnected ? 'Connected' : 'Not Connected'}</AlertTitle>
        <AlertDescription>
          {isConnected 
            ? 'Salesforce is connected and ready for use'
            : 'Connect to Salesforce to access all CRM features'
          }
        </AlertDescription>
      </Box>
      {!isConnected && (
        <Button 
          colorScheme="blue" 
          size="sm" 
          onClick={() => setConfigModalOpen(true)}
          isLoading={isConnecting}
        >
          Connect
        </Button>
      )}
      {isConnected && (
        <Button colorScheme="red" size="sm" onClick={() => setIsConnected(false)}>
          Disconnect
        </Button>
      )}
    </Alert>
  );

  // Render Dashboard
  const renderDashboard = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      {/* CRM Overview */}
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiUsers} color="blue.500" boxSize={8} />
              <Stat>
                <StatLabel>Users</StatLabel>
                <StatNumber>{users.length}</StatNumber>
                <StatHelpText>Total active users</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiTarget} color="green.500" boxSize={8} />
              <Stat>
                <StatLabel>Accounts</StatLabel>
                <StatNumber>{accounts.length}</StatNumber>
                <StatHelpText>Total customer accounts</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiPhone} color="orange.500" boxSize={8} />
              <Stat>
                <StatLabel>Contacts</StatLabel>
                <StatNumber>{contacts.length}</StatNumber>
                <StatHelpText>Total contacts</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiDollarSign} color="purple.500" boxSize={8} />
              <Stat>
                <StatLabel>Opportunities</StatLabel>
                <StatNumber>{opportunities.length}</StatNumber>
                <StatHelpText>Total opportunities</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Recent Activities */}
      <Card>
        <CardHeader>
          <HStack>
            <Icon as={FiActivity} color="blue.500" />
            <Heading size="md">Recent Activities</Heading>
          </HStack>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={3}>
            {opportunities.slice(0, 5).map((opportunity) => (
              <HStack key={opportunity.id} p={3} borderWidth="1px" borderRadius="md">
                <Avatar size="sm" name={opportunity.ownerName} />
                <VStack align="start" spacing={0}>
                  <Text fontWeight="medium">{opportunity.name}</Text>
                  <Text fontSize="sm" color="gray.500">
                    {opportunity.stageName} • {formatCurrency(opportunity.amount)}
                  </Text>
                  <Text fontSize="xs" color="gray.500">
                    {formatDateTime(opportunity.lastModifiedDate)}
                  </Text>
                </VStack>
              </HStack>
            ))}
          </VStack>
        </CardBody>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <Heading size="md">Quick Actions</Heading>
        </CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
            <Button 
              leftIcon={<FiPlus />}
              colorScheme="blue"
              onClick={() => {
                setModalMode('create');
                setFormData({ 
                  firstName: '', 
                  lastName: '', 
                  email: '', 
                  title: '',
                  phone: ''
                });
                setCreateModalOpen(true);
              }}
            >
              Create Contact
            </Button>
            <Button 
              leftIcon={<FiTarget />}
              colorScheme="green"
              onClick={() => setActiveTab('opportunities')}
            >
              View Opportunities
            </Button>
            <Button 
              leftIcon={<FiSettings />}
              colorScheme="orange"
              onClick={() => setActiveTab('settings')}
            >
              Manage Settings
            </Button>
            <Button 
              leftIcon={<FiTrendingUp />}
              colorScheme="purple"
              onClick={() => setActiveTab('analytics')}
            >
              View Analytics
            </Button>
          </SimpleGrid>
        </CardBody>
      </Card>
    </VStack>
  );

  // Render Accounts Management
  const renderAccounts = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Accounts Management</Heading>
        <HStack>
          <Input 
            placeholder="Search accounts..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
          <Button 
            leftIcon={<FiPlus />}
            colorScheme="blue"
            onClick={() => {
              setModalMode('create');
              setFormData({ name: '', type: '', industry: '' });
              setCreateModalOpen(true);
            }}
          >
            Create Account
          </Button>
        </HStack>
      </Flex>
      
      {filteredAccounts.length > 0 && (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Type</Th>
                <Th>Industry</Th>
                <Th>Annual Revenue</Th>
                <Th>Owner</Th>
                <Th>Created</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredAccounts.map((account) => (
                <Tr key={account.id}>
                  <Td>
                    <HStack>
                      <Icon as={FiBriefcase} color="gray.500" />
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">{account.name}</Text>
                        {account.description && (
                          <Text fontSize="sm" color="gray.600" noOfLines={2}>
                            {account.description}
                          </Text>
                        )}
                      </VStack>
                    </HStack>
                  </Td>
                  <Td>
                    <Badge colorScheme="blue">{account.type}</Badge>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{account.industry || '-'}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">
                      {account.annualRevenue ? formatCurrency(account.annualRevenue) : '-'}
                    </Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{account.ownerName || '-'}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{formatDate(account.createdDate)}</Text>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton 
                        icon={<FiEye />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(account);
                          setModalMode('view');
                          setDetailsModalOpen(true);
                        }}
                      />
                      <IconButton 
                        icon={<FiEdit2 />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(account);
                          setModalMode('edit');
                          setCreateModalOpen(true);
                        }}
                      />
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      )}
      
      {isLoading && (
        <Center py={8}>
          <VStack>
            <Spinner size="xl" />
            <Text>Loading accounts...</Text>
          </VStack>
        </Center>
      )}
    </VStack>
  );

  // Render Contacts Management
  const renderContacts = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Contacts Management</Heading>
        <HStack>
          <Input 
            placeholder="Search contacts..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
          <Button 
            leftIcon={<FiPlus />}
            colorScheme="blue"
            onClick={() => {
              setModalMode('create');
              setFormData({ 
                firstName: '', 
                lastName: '', 
                email: '', 
                title: '',
                phone: '',
                accountId: ''
              });
              setCreateModalOpen(true);
            }}
          >
            Create Contact
          </Button>
        </HStack>
      </Flex>
      
      {filteredContacts.length > 0 && (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Email</Th>
                <Th>Phone</Th>
                <Th>Title</Th>
                <Th>Account</Th>
                <Th>Created</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredContacts.map((contact) => (
                <Tr key={contact.id}>
                  <Td>
                    <HStack>
                      <Avatar size="sm" name={`${contact.firstName} ${contact.lastName}`} src={contact.photoUrl} />
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">
                          {contact.firstName} {contact.lastName}
                        </Text>
                        <Text fontSize="sm" color="gray.600">{contact.title}</Text>
                      </VStack>
                    </HStack>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{contact.email}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{contact.phone || contact.mobilePhone}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{contact.title}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{contact.accountName || '-'}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{formatDate(contact.createdDate)}</Text>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton 
                        icon={<FiEye />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(contact);
                          setModalMode('view');
                          setDetailsModalOpen(true);
                        }}
                      />
                      <IconButton 
                        icon={<FiEdit2 />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(contact);
                          setModalMode('edit');
                          setCreateModalOpen(true);
                        }}
                      />
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      )}
      
      {isLoading && (
        <Center py={8}>
          <VStack>
            <Spinner size="xl" />
            <Text>Loading contacts...</Text>
          </VStack>
        </Center>
      )}
    </VStack>
  );

  // Render Opportunities Management
  const renderOpportunities = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Opportunities Management</Heading>
        <HStack>
          <Input 
            placeholder="Search opportunities..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Select 
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            width="200px"
          >
            <option value="all">All Status</option>
            <option value="Prospecting">Prospecting</option>
            <option value="Qualification">Qualification</option>
            <option value="Needs Analysis">Needs Analysis</option>
            <option value="Value Proposition">Value Proposition</option>
            <option value="Id. Decision Makers">Id. Decision Makers</option>
            <option value="Perception Analysis">Perception Analysis</option>
            <option value="Proposal/Quote">Proposal/Quote</option>
            <option value="Negotiation/Review">Negotiation/Review</option>
            <option value="Closed Won">Closed Won</option>
            <option value="Closed Lost">Closed Lost</option>
          </Select>
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
          <Button 
            leftIcon={<FiPlus />}
            colorScheme="green"
            onClick={() => {
              setModalMode('create');
              setFormData({ 
                name: '', 
                accountId: '', 
                stageName: 'Prospecting',
                probability: 10,
                amount: 0,
                closeDate: ''
              });
              setCreateModalOpen(true);
            }}
          >
            Create Opportunity
          </Button>
        </HStack>
      </Flex>
      
      {filteredOpportunities.length > 0 && (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Account</Th>
                <Th>Stage</Th>
                <Th>Amount</Th>
                <Th>Probability</Th>
                <Th>Close Date</Th>
                <Th>Owner</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredOpportunities.map((opportunity) => (
                <Tr key={opportunity.id}>
                  <Td>
                    <VStack align="start" spacing={0}>
                      <Text fontWeight="medium">{opportunity.name}</Text>
                      <Text fontSize="sm" color="gray.600">{opportunity.type}</Text>
                    </VStack>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{opportunity.accountName || '-'}</Text>
                  </Td>
                  <Td>
                    <Badge colorScheme={getStatusColor(opportunity.stageName)}>
                      {opportunity.stageName}
                    </Badge>
                  </Td>
                  <Td>
                    <Text fontSize="sm">
                      {opportunity.amount ? formatCurrency(opportunity.amount) : '-'}
                    </Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{opportunity.probability}%</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{formatDate(opportunity.closeDate)}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{opportunity.ownerName || '-'}</Text>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton 
                        icon={<FiEye />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(opportunity);
                          setModalMode('view');
                          setDetailsModalOpen(true);
                        }}
                      />
                      <IconButton 
                        icon={<FiEdit2 />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(opportunity);
                          setModalMode('edit');
                          setCreateModalOpen(true);
                        }}
                      />
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      )}
      
      {isLoading && (
        <Center py={8}>
          <VStack>
            <Spinner size="xl" />
            <Text>Loading opportunities...</Text>
          </VStack>
        </Center>
      )}
    </VStack>
  );

  // Render Cases Management
  const renderCases = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Cases Management</Heading>
        <HStack>
          <Input 
            placeholder="Search cases..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Select 
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            width="200px"
          >
            <option value="all">All Status</option>
            <option value="New">New</option>
            <option value="Working">Working</option>
            <option value="Escalated">Escalated</option>
            <option value="Closed">Closed</option>
          </Select>
          <Select 
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            width="200px"
          >
            <option value="all">All Priority</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </Select>
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
          <Button 
            leftIcon={<FiPlus />}
            colorScheme="orange"
            onClick={() => {
              setModalMode('create');
              setFormData({ 
                subject: '', 
                description: '', 
                status: 'New',
                priority: 'Medium',
                type: '',
                origin: '',
                contactId: '',
                accountId: ''
              });
              setCreateModalOpen(true);
            }}
          >
            Create Case
          </Button>
        </HStack>
      </Flex>
      
      {filteredCases.length > 0 && (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Case Number</Th>
                <Th>Subject</Th>
                <Th>Status</Th>
                <Th>Priority</Th>
                <Th>Contact</Th>
                <Th>Account</Th>
                <Th>Owner</Th>
                <Th>Created</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredCases.map((case_) => (
                <Tr key={case_.id}>
                  <Td>
                    <Text fontWeight="medium">{case_.caseNumber}</Text>
                  </Td>
                  <Td>
                    <VStack align="start" spacing={0}>
                      <Text fontWeight="medium">{case_.subject}</Text>
                      <Text fontSize="sm" color="gray.600">{case_.type}</Text>
                    </VStack>
                  </Td>
                  <Td>
                    <Badge colorScheme={getStatusColor(case_.status)}>
                      {case_.status}
                    </Badge>
                  </Td>
                  <Td>
                    <Badge colorScheme={getPriorityColor(case_.priority)}>
                      {case_.priority}
                    </Badge>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{case_.contactName || '-'}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{case_.accountName || '-'}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{case_.ownerName || '-'}</Text>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{formatDate(case_.createdDate)}</Text>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton 
                        icon={<FiEye />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(case_);
                          setModalMode('view');
                          setDetailsModalOpen(true);
                        }}
                      />
                      <IconButton 
                        icon={<FiEdit2 />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(case_);
                          setModalMode('edit');
                          setCreateModalOpen(true);
                        }}
                      />
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      )}
      
      {isLoading && (
        <Center py={8}>
          <VStack>
            <Spinner size="xl" />
            <Text>Loading cases...</Text>
          </VStack>
        </Center>
      )}
    </VStack>
  );

  // Render Settings
  const renderSettings = () => (
    <VStack spacing={6} align="stretch">
      <Card>
        <CardHeader>
          <Heading size="lg">Salesforce Settings</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={6}>
            <Alert status="info">
              <AlertIcon as={FiInfo} />
              <Box>
                <AlertTitle>Configuration Status</AlertTitle>
                <AlertDescription>
                  {isConnected 
                    ? 'Salesforce is properly configured and connected'
                    : 'Configure Salesforce API settings to enable all features'
                  }
                </AlertDescription>
              </Box>
            </Alert>
            
            <FormControl>
              <FormLabel>Client ID</FormLabel>
              <Input 
                value={configData.clientId}
                onChange={(e) => setConfigData({ ...configData, clientId: e.target.value })}
                isDisabled={isConnected}
                placeholder="your-salesforce-client-id"
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Client Secret</FormLabel>
              <Input 
                type="password"
                value={configData.clientSecret}
                onChange={(e) => setConfigData({ ...configData, clientSecret: e.target.value })}
                isDisabled={isConnected}
                placeholder="your-salesforce-client-secret"
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Redirect URI</FormLabel>
              <Input 
                value={configData.redirectUri}
                onChange={(e) => setConfigData({ ...configData, redirectUri: e.target.value })}
                isDisabled={isConnected}
                placeholder="https://your-app.com/callback"
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Environment</FormLabel>
              <Select 
                value={configData.environment}
                onChange={(e) => setConfigData({ ...configData, environment: e.target.value as 'sandbox' | 'production' })}
                isDisabled={isConnected}
              >
                <option value="sandbox">Sandbox</option>
                <option value="production">Production</option>
              </Select>
            </FormControl>
            
            <FormControl>
              <FormLabel>API Version</FormLabel>
              <Input 
                value={configData.apiVersion}
                onChange={(e) => setConfigData({ ...configData, apiVersion: e.target.value })}
                isDisabled={isConnected}
                placeholder="56.0"
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Timeout (ms)</FormLabel>
              <NumberInput 
                value={configData.timeout}
                onChange={(value) => setConfigData({ ...configData, timeout: value })}
                min={1000}
                max={60000}
                isDisabled={isConnected}
              >
                <NumberInputField />
              </NumberInput>
            </FormControl>
            
            <FormControl>
              <FormLabel>Max Retries</FormLabel>
              <NumberInput 
                value={configData.maxRetries}
                onChange={(value) => setConfigData({ ...configData, maxRetries: value })}
                min={0}
                max={10}
                isDisabled={isConnected}
              >
                <NumberInputField />
              </NumberInput>
            </FormControl>
            
            <Button 
              colorScheme="blue" 
              leftIcon={<FiSettings />}
              onClick={() => setConfigModalOpen(true)}
              isDisabled={isConnected}
            >
              Configure Connection
            </Button>
          </VStack>
        </CardBody>
      </Card>
    </VStack>
  );

  // Load data when tab changes
  useEffect(() => {
    if (isConnected) {
      switch (activeTab) {
        case 'dashboard':
          loadDashboardData();
          break;
        case 'accounts':
          loadDashboardData();
          break;
        case 'contacts':
          loadDashboardData();
          break;
        case 'opportunities':
          loadDashboardData();
          break;
        case 'cases':
          loadDashboardData();
          break;
        default:
          break;
      }
    }
  }, [activeTab, isConnected]);

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack>
            <Icon as={FiDatabase} color="blue.500" boxSize={8} />
            <Heading size="xl">Salesforce CRM</Heading>
          </HStack>
          <ButtonGroup>
            <Button leftIcon={<FiRefreshCw />} onClick={() => window.location.reload()}>
              Reload
            </Button>
          </ButtonGroup>
        </HStack>

        {/* Tabs */}
        <Tabs 
          index={['dashboard', 'accounts', 'contacts', 'opportunities', 'cases', 'settings'].indexOf(activeTab)}
          onChange={(index) => setActiveTab(['dashboard', 'accounts', 'contacts', 'opportunities', 'cases', 'settings'][index])}
          variant="enclosed"
          colorScheme="blue"
        >
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Accounts</Tab>
            <Tab>Contacts</Tab>
            <Tab>Opportunities</Tab>
            <Tab>Cases</Tab>
            <Tab>Settings</Tab>
          </TabList>
          
          <TabPanels>
            <TabPanel>
              {renderDashboard()}
            </TabPanel>
            <TabPanel>
              {renderAccounts()}
            </TabPanel>
            <TabPanel>
              {renderContacts()}
            </TabPanel>
            <TabPanel>
              {renderOpportunities()}
            </TabPanel>
            <TabPanel>
              {renderCases()}
            </TabPanel>
            <TabPanel>
              {renderSettings()}
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>

      {/* Configuration Modal */}
      <Modal isOpen={configModalOpen} onClose={() => setConfigModalOpen(false)} size="md">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Configure Salesforce CRM</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <Alert status="info">
                <AlertIcon as={FiInfo} />
                <Box>
                  <AlertTitle>Configuration Required</AlertTitle>
                  <AlertDescription>
                    Enter your Salesforce Connected App credentials to connect to your CRM.
                  </AlertDescription>
                </Box>
              </Alert>
              
              <FormControl isInvalid={!configData.clientId}>
                <FormLabel>Client ID</FormLabel>
                <Input 
                  value={configData.clientId}
                  onChange={(e) => setConfigData({ ...configData, clientId: e.target.value })}
                  placeholder="your-salesforce-client-id"
                />
                <FormErrorMessage>Client ID is required</FormErrorMessage>
              </FormControl>
              
              <FormControl isInvalid={!configData.clientSecret}>
                <FormLabel>Client Secret</FormLabel>
                <Input 
                  type="password"
                  value={configData.clientSecret}
                  onChange={(e) => setConfigData({ ...configData, clientSecret: e.target.value })}
                  placeholder="your-salesforce-client-secret"
                />
                <FormErrorMessage>Client Secret is required</FormErrorMessage>
              </FormControl>
              
              <FormControl isInvalid={!configData.redirectUri}>
                <FormLabel>Redirect URI</FormLabel>
                <Input 
                  value={configData.redirectUri}
                  onChange={(e) => setConfigData({ ...configData, redirectUri: e.target.value })}
                  placeholder="https://your-app.com/callback"
                />
                <FormErrorMessage>Redirect URI is required</FormErrorMessage>
              </FormControl>
              
              <FormControl>
                <FormLabel>Environment</FormLabel>
                <Select 
                  value={configData.environment}
                  onChange={(e) => setConfigData({ ...configData, environment: e.target.value as 'sandbox' | 'production' })}
                >
                  <option value="sandbox">Sandbox</option>
                  <option value="production">Production</option>
                </Select>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={() => setConfigModalOpen(false)}>
              Cancel
            </Button>
            <Button 
              colorScheme="blue" 
              onClick={handleConnect}
              isLoading={isConnecting}
              isDisabled={!configData.clientId || !configData.clientSecret || !configData.redirectUri}
            >
              Connect
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create/Update Modal */}
      <Modal isOpen={createModalOpen} onClose={() => setCreateModalOpen(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {modalMode === 'create' ? 'Create' : 'Update'} {activeTab.slice(0, -1).slice(0, -1)}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              {/* Dynamic form fields based on active tab */}
              {activeTab === 'accounts' && (
                <>
                  <FormControl isInvalid={!formData.name}>
                    <FormLabel>Account Name</FormLabel>
                    <Input 
                      value={formData.name || ''}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Account name"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Type</FormLabel>
                    <Input 
                      value={formData.type || ''}
                      onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                      placeholder="Account type"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Industry</FormLabel>
                    <Input 
                      value={formData.industry || ''}
                      onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
                      placeholder="Industry"
                    />
                  </FormControl>
                </>
              )}
              
              {activeTab === 'contacts' && (
                <>
                  <FormControl isInvalid={!formData.firstName}>
                    <FormLabel>First Name</FormLabel>
                    <Input 
                      value={formData.firstName || ''}
                      onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                      placeholder="First name"
                    />
                  </FormControl>
                  
                  <FormControl isInvalid={!formData.lastName}>
                    <FormLabel>Last Name</FormLabel>
                    <Input 
                      value={formData.lastName || ''}
                      onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                      placeholder="Last name"
                    />
                  </FormControl>
                  
                  <FormControl isInvalid={!formData.email}>
                    <FormLabel>Email</FormLabel>
                    <Input 
                      value={formData.email || ''}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="Email address"
                      type="email"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Phone</FormLabel>
                    <Input 
                      value={formData.phone || ''}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="Phone number"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Title</FormLabel>
                    <Input 
                      value={formData.title || ''}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      placeholder="Job title"
                    />
                  </FormControl>
                </>
              )}
              
              {activeTab === 'opportunities' && (
                <>
                  <FormControl isInvalid={!formData.name}>
                    <FormLabel>Opportunity Name</FormLabel>
                    <Input 
                      value={formData.name || ''}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Opportunity name"
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Account</FormLabel>
                    <Select 
                      value={formData.accountId || ''}
                      onChange={(e) => setFormData({ ...formData, accountId: e.target.value })}
                    >
                      <option value="">Select Account</option>
                      {accounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.name}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Stage</FormLabel>
                    <Select 
                      value={formData.stageName || ''}
                      onChange={(e) => setFormData({ ...formData, stageName: e.target.value })}
                    >
                      <option value="Prospecting">Prospecting</option>
                      <option value="Qualification">Qualification</option>
                      <option value="Needs Analysis">Needs Analysis</option>
                      <option value="Value Proposition">Value Proposition</option>
                      <option value="Id. Decision Makers">Id. Decision Makers</option>
                      <option value="Perception Analysis">Perception Analysis</option>
                      <option value="Proposal/Quote">Proposal/Quote</option>
                      <option value="Negotiation/Review">Negotiation/Review</option>
                      <option value="Closed Won">Closed Won</option>
                      <option value="Closed Lost">Closed Lost</option>
                    </Select>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Probability (%)</FormLabel>
                    <NumberInput 
                      value={formData.probability || 0}
                      onChange={(value) => setFormData({ ...formData, probability: value })}
                      min={0}
                      max={100}
                    >
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Amount</FormLabel>
                    <NumberInput 
                      value={formData.amount || 0}
                      onChange={(value) => setFormData({ ...formData, amount: value })}
                      min={0}
                      precision={2}
                    >
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Close Date</FormLabel>
                    <Input 
                      value={formData.closeDate || ''}
                      onChange={(e) => setFormData({ ...formData, closeDate: e.target.value })}
                      type="date"
                    />
                  </FormControl>
                </>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button 
              colorScheme="blue" 
              onClick={() => {
                // Handle create/update logic based on active tab
                setCreateModalOpen(false);
              }}
              isDisabled={!formData.name || (activeTab === 'contacts' && !formData.email)}
            >
              {modalMode === 'create' ? 'Create' : 'Update'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  );
};

export default SalesforceManager;