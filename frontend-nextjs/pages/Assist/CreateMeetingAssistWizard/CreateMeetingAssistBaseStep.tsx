import React, { useState, Dispatch, SetStateAction } from "react";

import { dayjs } from "@lib/date-utils";
import TextField from "@components/TextField";
import Box from "@components/common/Box";
import Text from "@components/common/Text";

import { useToast } from "@chakra-ui/react";
import { Input, Box as ChakraBox, VStack, HStack } from "@chakra-ui/react";
import { NextApiRequest, NextApiResponse } from "next";
import supertokensNode from "supertokens-node";
import { backendConfig } from "../../../config/backendConfig";
import Session from "supertokens-node/recipe/session";

export async function getServerSideProps({
  req,
  res,
}: {
  req: NextApiRequest;
  res: NextApiResponse;
}) {
  // Notice how the server uses `API` from `withSSRContext`, instead of the top-level `API`.
  // const SSR = withSSRContext({ req })
  // this runs on the backend, so we must call init on supertokens-node SDK
  supertokensNode.init(backendConfig());
  let session;
  try {
    session = await Session.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return [];
      },
    });
  } catch (err: any) {
    if (err.type === Session.Error.TRY_REFRESH_TOKEN) {
      return { props: { fromSupertokens: "needs-refresh" } };
    } else if (err.type === Session.Error.UNAUTHORISED) {
      // this will force the frontend to try and refresh which will fail
      // clearing all cookies and redirecting the user to the login screen.
      return { props: { fromSupertokens: "needs-refresh" } };
    }
    throw err;
  }

  if (!session?.getUserId()) {
    return {
      redirect: {
        destination: "/User/Login/UserLogin",
        permanent: false,
      },
    };
  }

  return {
    props: {
      sub: session.getUserId(),
    },
  };
}

type Props = {
  notes: string;
  summary: string;
  windowStartDate: Date;
  windowEndDate: Date;
  location: string;
  setParentNotes: Dispatch<SetStateAction<string>>;
  setParentSummary: Dispatch<SetStateAction<string>>;
  setParentWindowStartDate: Dispatch<SetStateAction<Date>>;
  setParentWindowEndDate: Dispatch<SetStateAction<Date>>;
  setParentLocation: Dispatch<SetStateAction<string>>;
};

function CreateMeetingAssistBaseStep(props: Props) {
  const [notes, setNotes] = useState<string>(props?.notes);
  const [summary, setSummary] = useState<string>(props?.summary);
  const [windowStartDate, setWindowStartDate] = useState<Date>(
    props?.windowStartDate,
  );
  const [windowEndDate, setWindowEndDate] = useState<Date>(
    props?.windowEndDate,
  );
  const [location, setLocation] = useState<string>(props?.location);
  const [isStartDatePickerVisible, setIsStartDatePickerVisible] =
    useState<boolean>(false);
  const [isEndDatePickerVisible, setIsEndDatePickerVisible] =
    useState<boolean>(false);
  const [pageOffset, setPageOffset] = useState<number>(0);

  const setParentNotes = props?.setParentNotes;
  const setParentSummary = props?.setParentSummary;
  const setParentWindowStartDate = props?.setParentWindowStartDate;
  const setParentWindowEndDate = props?.setParentWindowEndDate;
  const setParentLocation = props?.setParentLocation;
  const toast = useToast();

  const changeNotes = (value: string) => {
    setNotes(value);
    setParentNotes(value);
  };

  const changeSummary = (value: string) => {
    setSummary(value);
    setParentSummary(value);
  };

  const changeWindowStartDate = (value: Date) => {
    setWindowStartDate(value);
    setParentWindowStartDate(value);
  };

  const changeWindowEndDate = (value: Date) => {
    setWindowEndDate(value);
    setParentWindowEndDate(value);
  };

  const changeLocation = (value: string) => {
    setLocation(value);
    setParentLocation(value);
  };

  const showStartDatePicker = () => {
    setIsStartDatePickerVisible(true);
  };

  const hideStartDatePicker = () => {
    setIsStartDatePickerVisible(false);
  };

  const showEndDatePicker = () => {
    setIsEndDatePickerVisible(true);
  };

  const hideEndDatePicker = () => {
    setIsEndDatePickerVisible(false);
  };

  return (
    <ChakraBox minH="65vh" maxH="65vh" w="100%">
      <VStack spacing={4} w="100%" align="center" overflowY="auto" maxH="65vh">
        <Text p={{ phone: "s", tablet: "m" }} variant="optionHeader" w="80%">
          Provide a time window for scheduling a meeting
        </Text>
        <ChakraBox p={{ phone: "s", tablet: "m" }} w="80%">
          <Text variant="optionHeader">Start</Text>
          <Input
            placeholder="Select Date and Time"
            size="md"
            type="datetime-local"
            onChange={(e) => {
              const durationMinutes = dayjs
                .duration(dayjs(windowEndDate).diff(dayjs(windowStartDate)))
                .asMinutes();
              const newEndDate = dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm")
                .add(durationMinutes, "minutes")
                .toDate();
              changeWindowStartDate(
                dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").toDate(),
              );
              changeWindowEndDate(newEndDate);
            }}
            value={dayjs(windowStartDate).format("YYYY-MM-DDTHH:mm")}
          />
        </ChakraBox>
        <ChakraBox p={{ phone: "s", tablet: "m" }} w="80%">
          <Text variant="optionHeader">End</Text>
          <Input
            placeholder="Select Date and Time"
            size="md"
            type="datetime-local"
            onChange={(e) => {
              const days = dayjs(e?.target?.value, "YYYY-MM-DDTHH:mm").diff(
                windowStartDate,
                "d",
              );
              console.log(days, " days");
              if (days > 6) {
                toast({
                  status: "info",
                  title: "Window too long",
                  description: "Time window cannot be longer than 7 days long",
                  duration: 9000,
                  isClosable: true,
                });

                changeWindowEndDate(
                  dayjs(windowStartDate).add(6, "d").hour(19).toDate(),
                );
                return;
              }

              const hours = dayjs(e?.target?.value).diff(windowStartDate, "h");

              if (hours < 2) {
                toast({
                  status: "info",
                  title: "Window too short",
                  description: "Time window should be at least 2 hours long",
                  duration: 9000,
                  isClosable: true,
                });
                changeWindowEndDate(
                  dayjs(windowStartDate).add(2, "h").toDate(),
                );
                return;
              }
              changeWindowEndDate(dayjs(e?.target?.value).toDate());
            }}
            value={dayjs(windowEndDate).format("YYYY-MM-DDTHH:mm")}
          />
        </ChakraBox>
        <ChakraBox p={{ phone: "s", tablet: "m" }} w="80%">
          <TextField
            label="Title"
            placeholder="title"
            multiline={true}
            rows={4}
            onChange={(e: { target: { value: string } }) =>
              changeSummary(e?.target?.value)
            }
            value={summary || props?.summary}
            style={{ width: "100%" }}
          />
        </ChakraBox>
        <ChakraBox p={{ phone: "s", tablet: "m" }} w="80%">
          <TextField
            label="Notes"
            multiline={true}
            rows={4}
            onChange={(e: { target: { value: string } }) =>
              changeNotes(e?.target?.value)
            }
            value={notes || props?.notes}
            style={{ width: "100%" }}
          />
        </ChakraBox>
        <ChakraBox p={{ phone: "s", tablet: "m" }} w="80%">
          <TextField
            label="Location"
            placeholder="location if any"
            onChange={(e: { target: { value: string } }) =>
              changeLocation(e?.target?.value)
            }
            value={location || props?.location}
            style={{ width: "100%" }}
          />
        </ChakraBox>
      </VStack>
    </ChakraBox>
  );
}

export default CreateMeetingAssistBaseStep;
