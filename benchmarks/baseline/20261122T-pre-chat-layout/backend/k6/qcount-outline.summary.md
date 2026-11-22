# k6 summary

scenario: outline

- http_req_duration: min=2.530, med=7.928, max=10.525, p(90)=10.465, p(95)=10.501, p(99)=10.520, avg=8.227
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- iterations: count=20.000, rate=4.779
- http_req_receiving: max=0.269, p(90)=0.222, p(95)=0.255, p(99)=0.266, avg=0.136, min=0.030, med=0.147
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_waiting: avg=8.048, min=2.450, med=7.739, max=10.321, p(90)=10.209, p(95)=10.272, p(99)=10.311
- http_req_blocked: p(95)=0.043, p(99)=0.101, avg=0.018, min=0.004, med=0.011, max=0.116, p(90)=0.023
- http_req_duration{expected_response:true}: min=2.530, med=7.928, max=10.525, p(90)=10.465, p(95)=10.501, p(99)=10.520, avg=8.227
- http_req_connecting: p(95)=0.004, p(99)=0.061, avg=0.004, min=0.000, med=0.000, max=0.075, p(90)=0.000
- http_req_sending: p(99)=0.064, avg=0.043, min=0.015, med=0.042, max=0.068, p(90)=0.050, p(95)=0.051
