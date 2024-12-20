model_name=CycleNetQQ

root_path_name=./dataset/
data_path_name=electricity.csv
model_id_name=Electricity
data_name=electricity

model_type='linear'
seq_lens=(96)
pred_lens=(720)

for seq_len in "${seq_lens[@]}"
do
  for pred_len in "${pred_lens[@]}"
  do
    for random_seed in 1024
    do
      python -u run.py \
        --is_training 0 \
        --root_path $root_path_name \
        --data_path $data_path_name \
        --model_id ${model_id_name}_${seq_len}_${pred_len} \
        --model $model_name \
        --data $data_name \
        --features M \
        --seq_len $seq_len \
        --pred_len $pred_len \
        --enc_in 321 \
        --cycle 168 \
        --model_type $model_type \
        --train_epochs 30 \
        --patience 5 \
        --itr 1 --batch_size 64 --learning_rate 0.01 --random_seed $random_seed
    done
  done
done