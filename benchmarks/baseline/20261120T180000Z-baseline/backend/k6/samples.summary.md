# k6 summary

scenario: samples

- http_req_blocked: avg=0.013, min=0.002, med=0.010, max=0.175, p(90)=0.014, p(95)=0.023, p(99)=0.158
- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.120, p(90)=0.000, p(95)=0.000, p(99)=0.116
- http_req_failed: rate=0.000
- http_req_waiting: p(90)=28.184, p(95)=30.373, p(99)=57.762, avg=20.181, min=7.270, med=18.010, max=60.698
- http_req_duration: p(95)=30.545, p(99)=57.973, avg=20.425, min=7.533, med=18.337, max=60.841, p(90)=28.480
- http_req_duration{expected_response:true}: min=7.533, med=18.337, max=60.841, p(90)=28.480, p(95)=30.545, p(99)=57.973, avg=20.425
- iterations: count=230.000, rate=22.566
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_sending: min=0.004, med=0.039, max=0.095, p(90)=0.053, p(95)=0.061, p(99)=0.071, avg=0.033
- http_req_receiving: avg=0.211, min=0.042, med=0.143, max=2.240, p(90)=0.456, p(95)=0.626, p(99)=0.960
- vus: min=5.000, max=5.000
