<?php

namespace App\Exports;

use App\Models\Professional;
use App\Support\ProfessionalPresenter;
use Illuminate\Database\Eloquent\Builder;
use OpenSpout\Common\Entity\Cell;
use OpenSpout\Common\Entity\Cell\EmptyCell;
use OpenSpout\Common\Entity\Cell\NumericCell;
use OpenSpout\Common\Entity\Cell\StringCell;
use OpenSpout\Common\Entity\Row;
use OpenSpout\Common\Entity\Style\Color;
use OpenSpout\Common\Entity\Style\Style;
use OpenSpout\Writer\XLSX\Options;
use OpenSpout\Writer\XLSX\Writer;

final class ProfessionalXlsxExporter
{
    private const array HEADERS = [
        'ФИО',
        'Телефон',
        'Город',
        'Область',
        'Страна',
        'Возраст',
        'Пол',
        'Опыт',
        'Фото',
        'Ресурс',
    ];

    /**
     * Потоково записывает отфильтрованных мастеров в XLSX без накопления в памяти.
     */
    public function write(Builder $query): void
    {
        $options = new Options;
        $options->DEFAULT_COLUMN_WIDTH = 18;
        $options->setColumnWidth(30, 1, 9);
        $options->setColumnWidth(20, 2, 3, 4, 5, 8, 10);

        $writer = new Writer($options);
        $writer->openToFile('php://output');

        try {
            $writer->getCurrentSheet()->setName('Мастера');
            $writer->addRow($this->headerRow());

            $query
                ->select([
                    'id',
                    'full_name',
                    'phone',
                    'city',
                    'region',
                    'country',
                    'age',
                    'gender',
                    'experience_text',
                    'photo_url',
                    'source',
                ])
                ->lazyById(250)
                ->each(fn (Professional $professional) => $writer->addRow(
                    $this->professionalRow($professional),
                ));
        } finally {
            $writer->close();
        }
    }

    /**
     * Создаёт выделенную строку заголовков книги.
     */
    private function headerRow(): Row
    {
        $style = (new Style)
            ->setFontBold()
            ->setFontColor(Color::WHITE)
            ->setBackgroundColor(Color::GREEN);

        return new Row(
            array_map(fn (string $value): Cell => new StringCell($value, $style), self::HEADERS),
        );
    }

    /**
     * Преобразует карточку мастера в безопасные типизированные ячейки Excel.
     */
    private function professionalRow(Professional $professional): Row
    {
        return new Row([
            $this->textCell($professional->full_name),
            $this->textCell($professional->phone),
            $this->textCell($professional->city),
            $this->textCell($professional->region),
            $this->textCell($professional->country),
            $this->numberCell($professional->age),
            $this->textCell(ProfessionalPresenter::gender($professional->gender)),
            $this->textCell($professional->experience_text),
            $this->textCell($professional->photo_url),
            $this->textCell($professional->source),
        ]);
    }

    /**
     * Всегда создаёт строковую ячейку, чтобы данные источника не стали формулой.
     */
    private function textCell(?string $value): Cell
    {
        return $value === null || $value === ''
            ? new EmptyCell(null, null)
            : new StringCell($value, null);
    }

    /**
     * Сохраняет возраст числом, а отсутствующее значение — пустой ячейкой.
     */
    private function numberCell(?int $value): Cell
    {
        return $value === null
            ? new EmptyCell(null, null)
            : new NumericCell($value, null);
    }
}
