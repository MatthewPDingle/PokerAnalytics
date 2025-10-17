import { Box, Heading, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

export type FeatureCardProps = {
  title: string;
  description: string;
  to: string;
};

const FeatureCard = ({ title, description, to }: FeatureCardProps) => (
  <Box
    as={RouterLink}
    to={to}
    p={6}
    borderRadius="xl"
    borderWidth="1px"
    borderColor="whiteAlpha.200"
    bg="blackAlpha.400"
    backdropFilter="blur(8px)"
    transition="transform 0.2s, box-shadow 0.2s"
    _hover={{ transform: 'translateY(-4px)', boxShadow: 'xl', textDecoration: 'none' }}
  >
    <VStack align="start" spacing={3}>
      <Heading size="md">{title}</Heading>
      <Text fontSize="sm" opacity={0.8}>
        {description}
      </Text>
    </VStack>
  </Box>
);

export default FeatureCard;
