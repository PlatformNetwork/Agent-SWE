import { render, screen, within } from '@testing-library/react';
import { SWRConfig } from 'swr';
import type { FootballMatch } from '../../footballMatchV2';
import type { FEFootballMatchHeader } from '../../frontend/feFootballMatchHeader';
import { FootballMatchHeader } from './FootballMatchHeader';

type Deferred<T> = { promise: Promise<T>; resolve: (value: T) => void };

const deferred = <T,>(): Deferred<T> => {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((res) => {
		resolve = res;
	});
	return { promise, resolve };
};

const renderWithSWR = (ui: React.ReactElement) =>
	render(<SWRConfig value={{ provider: () => new Map() }}>{ui}</SWRConfig>);

const makeFixtureMatch = (): FootballMatch => ({
	kind: 'Fixture',
	kickOff: new Date('2026-04-14T19:45:00Z'),
	homeTeam: { name: 'Green Town', paID: '101' },
	awayTeam: { name: 'Blue City', paID: '202' },
	paId: 'fixture-id',
});

const makeHeaderData = (): FEFootballMatchHeader => ({
	competitionName: 'La Liga',
	footballMatch: {
		id: 'match-id',
		date: '2026-04-14T19:45:00Z[Europe/London]',
		stage: { stageNumber: '2' },
		round: { roundNumber: '3' },
		leg: '1',
		homeTeam: {
			id: '101',
			name: 'Green Town',
			score: 2,
			scorers: 'Player One 12,Player Two 70',
		},
		awayTeam: {
			id: '202',
			name: 'Blue City',
			score: 1,
			scorers: 'Player Three 35',
		},
		type: 'MatchDay',
		liveMatch: true,
		result: false,
		previewAvailable: true,
		reportAvailable: true,
		lineupsAvailable: true,
		matchStatus: 'FT',
	},
	liveURL: 'https://example.com/live-feed',
	reportURL: 'https://example.com/match-report',
	infoURL: 'https://example.com/match-info',
});

describe('FootballMatchHeader', () => {
	it('renders placeholder then updates with fetched live data', async () => {
		const pending = deferred<unknown>();
		const getHeaderData = jest.fn(() => pending.promise);

		renderWithSWR(
			<FootballMatchHeader
				initialTab="live"
				initialData={undefined}
				edition="UK"
				getHeaderData={getHeaderData}
				refreshInterval={0}
				matchHeaderURL={new URL('https://example.com/match-header.json')}
			/>,
		);

		expect(
			document.querySelector('[data-name="placeholder"]'),
		).toBeInTheDocument();

		pending.resolve(makeHeaderData());

		const nav = await screen.findByRole('navigation');
		expect(getHeaderData).toHaveBeenCalled();
		expect(
			document.querySelector('[data-name="placeholder"]'),
		).toBeNull();
		const tabs = within(nav).getAllByRole('listitem');
		expect(tabs.length).toBe(3);
		expect(screen.getByLabelText('Score: 2')).toBeInTheDocument();
	});

	it('renders initial info tab then applies fetched league name', async () => {
		const pending = deferred<unknown>();
		const getHeaderData = jest.fn(() => pending.promise);
		const initialMatch = makeFixtureMatch();

		renderWithSWR(
			<FootballMatchHeader
				initialTab="info"
				initialData={{
					leagueName: 'Serie A',
					match: initialMatch,
					tabs: { matchKind: initialMatch.kind, selected: 'info' },
				}}
				edition="EUR"
				getHeaderData={getHeaderData}
				refreshInterval={0}
				matchHeaderURL={new URL('https://example.com/match-header.json')}
			/>,
		);

		const initialNav = screen.getByRole('navigation');
		expect(getHeaderData).toHaveBeenCalled();
		expect(within(initialNav).getAllByRole('listitem').length).toBe(1);
		expect(screen.getByText('Serie A')).toBeInTheDocument();

		pending.resolve(makeHeaderData());

		expect(await screen.findByText('La Liga')).toBeInTheDocument();
		const nav = screen.getByRole('navigation');
		const tabs = within(nav).getAllByRole('listitem');
		expect(tabs.length).toBeGreaterThanOrEqual(1);
		const matchReportLink = within(nav).getByRole('link', {
			name: 'Match report',
		});
		expect(matchReportLink).toHaveAttribute(
			'href',
			'https://example.com/match-report',
		);
	});
});
