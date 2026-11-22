# k6 summary

scenario: samples

- iterations: count=20.000, rate=4.562
- http_req_blocked: p(95)=0.043, p(99)=0.384, avg=0.034, min=0.003, med=0.011, max=0.469, p(90)=0.014
- http_req_waiting: p(95)=26.319, p(99)=27.985, avg=18.047, min=7.398, med=21.297, max=28.401, p(90)=26.145
- http_req_receiving: p(95)=0.227, p(99)=0.253, avg=0.117, min=0.053, med=0.099, max=0.259, p(90)=0.209
- http_req_duration{expected_response:true}: min=7.585, med=21.463, max=28.593, p(90)=26.349, p(95)=26.502, p(99)=28.174, avg=18.208
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_duration: p(95)=26.502, p(99)=28.174, avg=18.208, min=7.585, med=21.463, max=28.593, p(90)=26.349
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_sending: p(99)=0.067, avg=0.044, min=0.013, med=0.045, max=0.069, p(90)=0.056, p(95)=0.058
- http_req_connecting: med=0.000, max=0.159, p(90)=0.000, p(95)=0.008, p(99)=0.128, avg=0.008, min=0.000
